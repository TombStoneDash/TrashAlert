"""
Comprehensive tests for service layer.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.models import Address, CrowdReport, CrowdConsensus
from app.services import ConsensusService, LookupService, ReportService


@pytest.fixture
def db_session():
    """Create a fresh database session for each test."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


class TestConsensusService:
    """Test suite for ConsensusService."""

    def test_calculate_consensus_single_report(self, db_session):
        """Test consensus with single report (unverified)."""
        # Create address
        addr = Address(normalized_address="TEST", city="TEST", lat=32.0, lon=-117.0)
        db_session.add(addr)
        db_session.commit()

        # Create single report
        report = CrowdReport(
            address_id=addr.id,
            trash_day="MON",
            recycling_day="WED",
            green_day="FRI",
        )
        db_session.add(report)
        db_session.commit()

        # Calculate consensus
        service = ConsensusService(db_session)
        consensus = service.calculate_consensus(addr.id)

        assert consensus is not None
        assert consensus.consensus_trash_day == "MON"
        assert consensus.consensus_recycling_day == "WED"
        assert consensus.consensus_green_day == "FRI"
        assert consensus.total_reports == 1
        assert consensus.is_verified is False  # Not enough reports

    def test_calculate_consensus_verified(self, db_session):
        """Test consensus with enough reports for verification."""
        # Create address
        addr = Address(normalized_address="TEST", city="TEST", lat=32.0, lon=-117.0)
        db_session.add(addr)
        db_session.commit()

        # Create 4 reports with 3 agreeing (75% agreement)
        reports = [
            CrowdReport(address_id=addr.id, trash_day="MON", recycling_day="WED"),
            CrowdReport(address_id=addr.id, trash_day="MON", recycling_day="WED"),
            CrowdReport(address_id=addr.id, trash_day="MON", recycling_day="WED"),
            CrowdReport(address_id=addr.id, trash_day="TUE", recycling_day="THU"),
        ]
        db_session.add_all(reports)
        db_session.commit()

        # Calculate consensus
        service = ConsensusService(db_session)
        consensus = service.calculate_consensus(addr.id)

        assert consensus is not None
        assert consensus.consensus_trash_day == "MON"  # Most common
        assert consensus.total_reports == 4
        assert consensus.trash_agreement_ratio == 0.75
        assert consensus.is_verified is True  # >=3 reports, >=75% agreement

    def test_calculate_consensus_not_verified_low_agreement(self, db_session):
        """Test consensus with reports but low agreement."""
        # Create address
        addr = Address(normalized_address="TEST", city="TEST", lat=32.0, lon=-117.0)
        db_session.add(addr)
        db_session.commit()

        # Create 4 reports with no majority
        reports = [
            CrowdReport(address_id=addr.id, trash_day="MON"),
            CrowdReport(address_id=addr.id, trash_day="TUE"),
            CrowdReport(address_id=addr.id, trash_day="WED"),
            CrowdReport(address_id=addr.id, trash_day="THU"),
        ]
        db_session.add_all(reports)
        db_session.commit()

        # Calculate consensus
        service = ConsensusService(db_session)
        consensus = service.calculate_consensus(addr.id)

        assert consensus is not None
        assert consensus.total_reports == 4
        assert consensus.trash_agreement_ratio == 0.25  # Only 1/4 agree
        assert consensus.is_verified is False  # Low agreement

    def test_calculate_consensus_no_reports(self, db_session):
        """Test consensus with no reports (should delete existing)."""
        # Create address with existing consensus
        addr = Address(normalized_address="TEST", city="TEST", lat=32.0, lon=-117.0)
        db_session.add(addr)
        db_session.commit()

        consensus_existing = CrowdConsensus(
            address_id=addr.id,
            consensus_trash_day="MON",
            total_reports=1,
            trash_agreement_ratio=1.0,
            is_verified=False,
        )
        db_session.add(consensus_existing)
        db_session.commit()

        # Calculate consensus with no reports
        service = ConsensusService(db_session)
        consensus = service.calculate_consensus(addr.id)

        assert consensus is None
        assert db_session.query(CrowdConsensus).filter(
            CrowdConsensus.address_id == addr.id
        ).first() is None


class TestLookupService:
    """Test suite for LookupService."""

    def test_lookup_by_address_not_found(self, db_session):
        """Test lookup for non-existent address."""
        service = LookupService(db_session)
        result = service.lookup_by_address("123 Nowhere St, Unknown City, CA")

        assert result["data_source"] == "UNKNOWN"
        assert result["trash_day_of_week"] is None
        assert result["matched_address"] == "123 Nowhere St, Unknown City, CA"

    def test_lookup_by_address_official_data(self, db_session):
        """Test lookup with official data."""
        # Create address with official data
        addr = Address(
            normalized_address="123 MAIN ST, SAN DIEGO, CA",
            city="SAN DIEGO",
            city_id="san_diego",
            lat=32.7157,
            lon=-117.1611,
            official_trash_day="MON",
            official_recycling_day="WED",
            official_green_day="FRI",
        )
        db_session.add(addr)
        db_session.commit()

        service = LookupService(db_session)
        result = service.lookup_by_address("123 Main St, San Diego, CA")

        assert result["data_source"] == "OFFICIAL"
        assert result["trash_day_of_week"] == "Monday"
        assert result["recycling_day_of_week"] == "Wednesday"
        assert result["green_waste_day_of_week"] == "Friday"

    def test_lookup_by_address_crowd_verified(self, db_session):
        """Test lookup with verified crowdsourced data."""
        # Create address
        addr = Address(
            normalized_address="456 ELM AVE, FRESNO, CA",
            city="FRESNO",
            city_id="fresno",
            lat=36.7378,
            lon=-119.7871,
        )
        db_session.add(addr)
        db_session.commit()

        # Create verified consensus
        consensus = CrowdConsensus(
            address_id=addr.id,
            consensus_trash_day="TUE",
            consensus_recycling_day="THU",
            consensus_green_day=None,
            total_reports=5,
            trash_agreement_ratio=0.9,
            recycling_agreement_ratio=0.85,
            green_agreement_ratio=0.0,
            is_verified=True,
        )
        db_session.add(consensus)
        db_session.commit()

        service = LookupService(db_session)
        result = service.lookup_by_address("456 Elm Ave, Fresno, CA")

        assert result["data_source"] == "CROWD_VERIFIED"
        assert result["trash_day_of_week"] == "Tuesday"
        assert result["recycling_day_of_week"] == "Thursday"
        assert result["consensus_reports_count"] == 5

    def test_lookup_by_address_crowd_unverified(self, db_session):
        """Test lookup with unverified crowdsourced data."""
        # Create address without official data
        addr = Address(
            normalized_address="789 OAK RD, CALEXICO, CA",
            city="CALEXICO",
            city_id="calexico",
            lat=32.679,
            lon=-115.499,
        )
        db_session.add(addr)
        db_session.commit()

        # Create unverified consensus
        consensus = CrowdConsensus(
            address_id=addr.id,
            consensus_trash_day="WED",
            total_reports=2,
            trash_agreement_ratio=0.5,
            recycling_agreement_ratio=0.0,
            green_agreement_ratio=0.0,
            is_verified=False,
        )
        db_session.add(consensus)
        db_session.commit()

        service = LookupService(db_session)
        result = service.lookup_by_address("789 Oak Rd, Calexico, CA")

        assert result["data_source"] == "CROWD_UNVERIFIED"
        assert result["trash_day_of_week"] == "Wednesday"
        assert result["consensus_reports_count"] == 2

    def test_lookup_priority_crowd_over_official(self, db_session):
        """Test that verified crowd data takes priority over official data."""
        # Create address with both official and verified crowd data
        addr = Address(
            normalized_address="321 PINE ST, IMPERIAL, CA",
            city="IMPERIAL",
            city_id="imperial",
            lat=32.8473,
            lon=-115.5694,
            official_trash_day="MON",  # Official says Monday
        )
        db_session.add(addr)
        db_session.commit()

        # Verified consensus says Tuesday (should override)
        consensus = CrowdConsensus(
            address_id=addr.id,
            consensus_trash_day="TUE",
            total_reports=5,
            trash_agreement_ratio=0.9,
            recycling_agreement_ratio=0.0,
            green_agreement_ratio=0.0,
            is_verified=True,
        )
        db_session.add(consensus)
        db_session.commit()

        service = LookupService(db_session)
        result = service.lookup_by_address("321 Pine St, Imperial, CA")

        assert result["data_source"] == "CROWD_VERIFIED"
        assert result["trash_day_of_week"] == "Tuesday"  # Crowd data wins

    def test_lookup_by_coordinates(self, db_session):
        """Test lookup by coordinates."""
        # Create address
        addr = Address(
            normalized_address="555 BEACH BLVD, SAN DIEGO, CA",
            city="SAN DIEGO",
            city_id="san_diego",
            lat=32.7157,
            lon=-117.1611,
            official_trash_day="FRI",
        )
        db_session.add(addr)
        db_session.commit()

        service = LookupService(db_session)
        # Lookup nearby coordinates
        result = service.lookup_by_coordinates(lat=32.7158, lon=-117.1612)

        assert result["data_source"] == "OFFICIAL"
        assert result["trash_day_of_week"] == "Friday"
        assert result["matched_address"] == "555 BEACH BLVD, SAN DIEGO, CA"


class TestReportService:
    """Test suite for ReportService."""

    def test_submit_report_new_address(self, db_session):
        """Test submitting report for new address."""
        service = ReportService(db_session)

        address, consensus = service.submit_report(
            address_str="999 New St, El Centro, CA",
            trash_day="Monday",
            recycling_day="Wednesday",
            green_day="Friday",
            user_hash="test_user",
            ip_address="192.168.1.1",
        )

        assert address is not None
        assert address.id is not None
        assert "999 NEW ST" in address.normalized_address

        assert consensus is not None
        assert consensus.consensus_trash_day == "MON"
        assert consensus.consensus_recycling_day == "WED"
        assert consensus.consensus_green_day == "FRI"
        assert consensus.total_reports == 1
        assert consensus.is_verified is False

    def test_submit_report_existing_address(self, db_session):
        """Test submitting multiple reports for same address."""
        service = ReportService(db_session)

        # Submit first report
        addr1, consensus1 = service.submit_report(
            address_str="111 Test Ave, Brawley, CA",
            trash_day="MON",
            recycling_day="WED",
            green_day=None,
        )

        # Submit second report (same address)
        addr2, consensus2 = service.submit_report(
            address_str="111 Test Ave, Brawley, CA",
            trash_day="MON",
            recycling_day="WED",
            green_day=None,
        )

        # Should be same address
        assert addr1.id == addr2.id

        # Consensus should be updated
        assert consensus2.total_reports == 2

    def test_submit_report_builds_consensus(self, db_session):
        """Test that multiple reports build consensus."""
        service = ReportService(db_session)

        address_str = "222 Consensus St, Holtville, CA"

        # Submit 3 agreeing reports + 1 disagreeing
        service.submit_report(address_str, trash_day="TUE", recycling_day=None, green_day=None)
        service.submit_report(address_str, trash_day="TUE", recycling_day=None, green_day=None)
        service.submit_report(address_str, trash_day="TUE", recycling_day=None, green_day=None)
        addr, consensus = service.submit_report(
            address_str, trash_day="WED", recycling_day=None, green_day=None
        )

        assert consensus.total_reports == 4
        assert consensus.consensus_trash_day == "TUE"  # Most common
        assert consensus.trash_agreement_ratio == 0.75  # 3/4
        assert consensus.is_verified is True  # >=3 reports, >=75%

    def test_submit_report_validates_days(self, db_session):
        """Test that invalid days are rejected."""
        service = ReportService(db_session)

        address, consensus = service.submit_report(
            address_str="333 Invalid St, Test, CA",
            trash_day="INVALID_DAY",
            recycling_day="Monday",
            green_day=None,
        )

        # Invalid trash day should be None
        assert consensus.consensus_trash_day is None
        # Valid recycling day should be normalized
        assert consensus.consensus_recycling_day == "MON"

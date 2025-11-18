"""
Business logic services for TrashAlert.

This module provides a clean separation between API endpoints and business logic,
making the code more maintainable and testable.
"""
from typing import Optional, Dict, Any, Tuple, List
from collections import Counter
from sqlalchemy.orm import Session
import logging

from app.repositories import (
    AddressRepository,
    CrowdReportRepository,
    CrowdConsensusRepository,
    MetricsRepository,
)
from app.models import Address, CrowdConsensus
from app.utils import validate_day, day_abbrev_to_full, get_city_name_from_id

logger = logging.getLogger(__name__)


class ConsensusService:
    """Service for managing crowdsourced consensus calculations."""

    # Consensus verification thresholds
    MIN_REPORTS_FOR_VERIFICATION = 3
    MIN_AGREEMENT_RATIO = 0.75

    def __init__(self, db: Session):
        """
        Initialize the service.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        self.report_repo = CrowdReportRepository(db)
        self.consensus_repo = CrowdConsensusRepository(db)

    def calculate_consensus(self, address_id: int) -> Optional[CrowdConsensus]:
        """
        Calculate and update consensus for an address based on all reports.

        Logic:
        - Aggregates all reports for the address
        - Calculates most common value for each day type
        - Calculates agreement ratios
        - Marks as verified if: total_reports >= 3 AND agreement_ratio >= 0.75

        Args:
            address_id: Address ID to calculate consensus for

        Returns:
            Updated CrowdConsensus object or None if no reports
        """
        # Get all reports for this address
        reports = self.report_repo.get_by_address_id(address_id)

        if not reports:
            # No reports, remove consensus if it exists
            self.consensus_repo.delete_by_address_id(address_id)
            return None

        # Aggregate reports by day type
        trash_days = [r.trash_day for r in reports if r.trash_day]
        recycling_days = [r.recycling_day for r in reports if r.recycling_day]
        green_days = [r.green_day for r in reports if r.green_day]

        total_reports = len(reports)

        # Calculate consensus (most common value) and agreement ratios
        trash_consensus, trash_ratio = self._get_consensus_and_ratio(trash_days)
        recycling_consensus, recycling_ratio = self._get_consensus_and_ratio(
            recycling_days
        )
        green_consensus, green_ratio = self._get_consensus_and_ratio(green_days)

        # Overall agreement ratio (average of available ratios)
        ratios = [r for r in [trash_ratio, recycling_ratio, green_ratio] if r > 0]
        avg_ratio = sum(ratios) / len(ratios) if ratios else 0.0

        # Verification check
        is_verified = (
            total_reports >= self.MIN_REPORTS_FOR_VERIFICATION
            and avg_ratio >= self.MIN_AGREEMENT_RATIO
        )

        # Update or create consensus
        consensus = self.consensus_repo.update_or_create(
            address_id=address_id,
            consensus_trash_day=trash_consensus,
            consensus_recycling_day=recycling_consensus,
            consensus_green_day=green_consensus,
            total_reports=total_reports,
            trash_agreement_ratio=trash_ratio,
            recycling_agreement_ratio=recycling_ratio,
            green_agreement_ratio=green_ratio,
            is_verified=is_verified,
        )

        return consensus

    def _get_consensus_and_ratio(
        self, values: List[str]
    ) -> Tuple[Optional[str], float]:
        """
        Calculate consensus (most common value) and agreement ratio.

        Args:
            values: List of values to analyze

        Returns:
            Tuple of (consensus_value, agreement_ratio)
        """
        if not values:
            return None, 0.0

        counter = Counter(values)
        most_common = counter.most_common(1)[0]
        consensus_value = most_common[0]
        agreement_ratio = most_common[1] / len(values)

        return consensus_value, agreement_ratio


class LookupService:
    """Service for address lookup operations."""

    def __init__(self, db: Session):
        """
        Initialize the service.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        self.address_repo = AddressRepository(db)
        self.consensus_repo = CrowdConsensusRepository(db)

    def lookup_by_address(
        self, address_str: str, city_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Look up pickup schedule by address string.

        Args:
            address_str: Address string
            city_id: Optional city ID filter

        Returns:
            Dictionary with lookup results
        """
        from app.utils import normalize_address

        # Normalize address
        parts = normalize_address(address_str)
        normalized = parts["normalized_address"]
        city_name = parts.get("city")

        # Get city_id from city name if not provided
        if not city_id and city_name:
            from app.utils import get_city_id_from_name

            city_id = get_city_id_from_name(city_name)

        # Find address
        addr_record = self.address_repo.get_by_normalized_address(normalized, city_id)

        if not addr_record:
            return {
                "matched_address": address_str,
                "city_id": city_id,
                "city_name": city_name,
                "lat": None,
                "lon": None,
                "trash_day_of_week": None,
                "recycling_day_of_week": None,
                "green_waste_day_of_week": None,
                "data_source": "UNKNOWN",
                "consensus_reports_count": None,
                "consensus_agreement_ratio": None,
            }

        return self._build_lookup_response(addr_record)

    def lookup_by_coordinates(
        self, lat: float, lon: float, city_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Look up pickup schedule by coordinates.

        Args:
            lat: Latitude
            lon: Longitude
            city_id: Optional city ID filter

        Returns:
            Dictionary with lookup results
        """
        # Find address by coordinates
        addr_record = self.address_repo.find_by_coordinates(
            lat=lat, lon=lon, max_distance_meters=50, city_id=city_id
        )

        if not addr_record:
            return {
                "matched_address": f"({lat}, {lon})",
                "city_id": city_id,
                "city_name": get_city_name_from_id(city_id) if city_id else None,
                "lat": lat,
                "lon": lon,
                "trash_day_of_week": None,
                "recycling_day_of_week": None,
                "green_waste_day_of_week": None,
                "data_source": "UNKNOWN",
                "consensus_reports_count": None,
                "consensus_agreement_ratio": None,
            }

        return self._build_lookup_response(addr_record)

    def _build_lookup_response(self, addr_record: Address) -> Dict[str, Any]:
        """
        Build lookup response with data source priority logic.

        Data source priority:
        1. CROWD_VERIFIED - Verified crowdsourced consensus
        2. OFFICIAL - Official municipal data
        3. CROWD_UNVERIFIED - Unverified crowdsourced data
        4. UNKNOWN - No data available

        Args:
            addr_record: Address database record

        Returns:
            Dictionary with lookup response data
        """
        # Get consensus data
        consensus = self.consensus_repo.get_by_address_id(addr_record.id)

        # Apply source priority logic
        data_source = "UNKNOWN"
        trash_day = None
        recycling_day = None
        green_day = None
        consensus_reports_count = None
        consensus_agreement_ratio = None

        # Priority 1: CROWD_VERIFIED
        if consensus and consensus.is_verified:
            data_source = "CROWD_VERIFIED"
            trash_day = consensus.consensus_trash_day
            recycling_day = consensus.consensus_recycling_day
            green_day = consensus.consensus_green_day
            consensus_reports_count = consensus.total_reports
            consensus_agreement_ratio = self._calculate_overall_agreement_ratio(
                consensus
            )

        # Priority 2: OFFICIAL
        elif any(
            [
                addr_record.official_trash_day,
                addr_record.official_recycling_day,
                addr_record.official_green_day,
            ]
        ):
            data_source = "OFFICIAL"
            trash_day = addr_record.official_trash_day
            recycling_day = addr_record.official_recycling_day
            green_day = addr_record.official_green_day

        # Priority 3: CROWD_UNVERIFIED
        elif consensus:
            data_source = "CROWD_UNVERIFIED"
            trash_day = consensus.consensus_trash_day
            recycling_day = consensus.consensus_recycling_day
            green_day = consensus.consensus_green_day
            consensus_reports_count = consensus.total_reports
            consensus_agreement_ratio = self._calculate_overall_agreement_ratio(
                consensus
            )

        # Convert day abbreviations to full names
        trash_day_full = day_abbrev_to_full(trash_day)
        recycling_day_full = day_abbrev_to_full(recycling_day)
        green_day_full = day_abbrev_to_full(green_day)

        return {
            "matched_address": addr_record.normalized_address,
            "city_id": addr_record.city_id,
            "city_name": addr_record.city,
            "lat": addr_record.lat,
            "lon": addr_record.lon,
            "trash_day_of_week": trash_day_full,
            "recycling_day_of_week": recycling_day_full,
            "green_waste_day_of_week": green_day_full,
            "data_source": data_source,
            "consensus_reports_count": consensus_reports_count,
            "consensus_agreement_ratio": consensus_agreement_ratio,
        }

    def _calculate_overall_agreement_ratio(
        self, consensus: CrowdConsensus
    ) -> float:
        """
        Calculate overall agreement ratio from consensus.

        Args:
            consensus: CrowdConsensus object

        Returns:
            Overall agreement ratio
        """
        ratios = [
            r
            for r in [
                consensus.trash_agreement_ratio,
                consensus.recycling_agreement_ratio,
                consensus.green_agreement_ratio,
            ]
            if r > 0
        ]
        return round(sum(ratios) / len(ratios), 2) if ratios else 0.0


class ReportService:
    """Service for managing crowdsourced reports."""

    def __init__(self, db: Session):
        """
        Initialize the service.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        self.address_repo = AddressRepository(db)
        self.report_repo = CrowdReportRepository(db)
        self.consensus_service = ConsensusService(db)

    def submit_report(
        self,
        address_str: str,
        trash_day: Optional[str],
        recycling_day: Optional[str],
        green_day: Optional[str],
        user_hash: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> Tuple[Address, CrowdConsensus]:
        """
        Submit a crowdsourced report and update consensus.

        Args:
            address_str: Address string
            trash_day: Trash pickup day
            recycling_day: Recycling pickup day
            green_day: Green waste pickup day
            user_hash: User identifier hash
            ip_address: User IP address

        Returns:
            Tuple of (Address, CrowdConsensus)
        """
        # Validate days
        trash_day = validate_day(trash_day)
        recycling_day = validate_day(recycling_day)
        green_day = validate_day(green_day)

        # Find or create address
        address = self.address_repo.find_or_create(address_str)

        # Create report
        self.report_repo.create(
            address_id=address.id,
            trash_day=trash_day,
            recycling_day=recycling_day,
            green_day=green_day,
            user_hash=user_hash,
            ip_address=ip_address,
        )

        # Update consensus
        consensus = self.consensus_service.calculate_consensus(address.id)

        return address, consensus

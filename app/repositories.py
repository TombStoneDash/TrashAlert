"""
Repository pattern implementation for database operations.

This module provides a clean separation between business logic and data access,
making the code more maintainable and testable.
"""
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from geopy.distance import geodesic
import logging

from app.models import Address, CrowdReport, CrowdConsensus, RequestMetrics
from app.utils import normalize_address, get_city_id_from_name

logger = logging.getLogger(__name__)


class AddressRepository:
    """Repository for Address model operations."""

    def __init__(self, db: Session):
        """
        Initialize the repository.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db

    def get_by_id(self, address_id: int) -> Optional[Address]:
        """
        Get an address by ID.

        Args:
            address_id: Address ID

        Returns:
            Address object or None if not found
        """
        return self.db.query(Address).filter(Address.id == address_id).first()

    def get_by_normalized_address(
        self, normalized_address: str, city_id: Optional[str] = None
    ) -> Optional[Address]:
        """
        Get an address by normalized address string.

        Args:
            normalized_address: Normalized address string
            city_id: Optional city ID filter

        Returns:
            Address object or None if not found
        """
        query = self.db.query(Address).filter(
            Address.normalized_address == normalized_address
        )

        if city_id:
            query = query.filter(Address.city_id == city_id)

        return query.first()

    def find_by_coordinates(
        self,
        lat: float,
        lon: float,
        max_distance_meters: float = 50,
        city_id: Optional[str] = None,
    ) -> Optional[Address]:
        """
        Find the nearest address to given coordinates.

        Uses a bounding box query for efficiency, then calculates actual distance.

        Args:
            lat: Latitude
            lon: Longitude
            max_distance_meters: Maximum distance in meters
            city_id: Optional city ID filter

        Returns:
            Nearest Address object or None
        """
        # Calculate bounding box
        lat_delta = max_distance_meters / 111000.0 * 1.5
        lon_delta = (
            max_distance_meters / (111000.0 * abs(float(lat))) * 1.5
            if lat != 0
            else lat_delta
        )

        # Build query with bounding box
        query = self.db.query(Address).filter(
            Address.lat.isnot(None),
            Address.lon.isnot(None),
            Address.lat.between(lat - lat_delta, lat + lat_delta),
            Address.lon.between(lon - lon_delta, lon + lon_delta),
        )

        if city_id:
            query = query.filter(Address.city_id == city_id)

        candidates = query.limit(100).all()

        if not candidates:
            return None

        # Find nearest within max distance
        nearest = None
        min_distance = float("inf")

        for addr in candidates:
            distance = geodesic((lat, lon), (addr.lat, addr.lon)).meters
            if distance < min_distance and distance <= max_distance_meters:
                min_distance = distance
                nearest = addr

        return nearest

    def find_or_create(
        self,
        address_str: str,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
    ) -> Address:
        """
        Find existing address or create new one.

        Args:
            address_str: Raw address string
            lat: Optional latitude
            lon: Optional longitude

        Returns:
            Address object (existing or newly created)
        """
        # Normalize the address
        parts = normalize_address(address_str)
        normalized = parts["normalized_address"]

        # Try to find existing by normalized string
        existing = self.get_by_normalized_address(normalized)
        if existing:
            return existing

        # If coordinates provided, try to find nearby address
        if lat and lon:
            nearby = self.find_by_coordinates(lat, lon, max_distance_meters=50)
            if nearby:
                return nearby

        # Create new address
        city_id = get_city_id_from_name(parts["city"]) if parts["city"] else None

        new_address = Address(
            normalized_address=normalized,
            house_number=parts["house_number"],
            street=parts["street"],
            city=parts["city"],
            city_id=city_id,
            city_name=parts["city"],
            state=parts["state"],
            zip_code=parts["zip_code"],
            lat=lat,
            lon=lon,
        )
        self.db.add(new_address)
        self.db.commit()
        self.db.refresh(new_address)

        logger.info(f"Created new address: {normalized} (ID: {new_address.id})")
        return new_address

    def get_stats_by_city(self) -> List[Dict[str, Any]]:
        """
        Get address count statistics grouped by city.

        Returns:
            List of dictionaries with city and address count
        """
        city_stats = (
            self.db.query(Address.city, func.count(Address.id).label("address_count"))
            .group_by(Address.city)
            .order_by(Address.city)
            .all()
        )

        return [
            {"city": city, "address_count": count}
            for city, count in city_stats
            if city
        ]

    def count(self) -> int:
        """
        Get total count of addresses.

        Returns:
            Total number of addresses
        """
        return self.db.query(Address).count()


class CrowdReportRepository:
    """Repository for CrowdReport model operations."""

    def __init__(self, db: Session):
        """
        Initialize the repository.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db

    def create(
        self,
        address_id: int,
        trash_day: Optional[str] = None,
        recycling_day: Optional[str] = None,
        green_day: Optional[str] = None,
        user_hash: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> CrowdReport:
        """
        Create a new crowd report.

        Args:
            address_id: Address ID
            trash_day: Trash pickup day
            recycling_day: Recycling pickup day
            green_day: Green waste pickup day
            user_hash: User identifier hash
            ip_address: User IP address

        Returns:
            Created CrowdReport object
        """
        report = CrowdReport(
            address_id=address_id,
            trash_day=trash_day,
            recycling_day=recycling_day,
            green_day=green_day,
            user_hash=user_hash,
            ip_address=ip_address,
        )
        self.db.add(report)
        self.db.commit()
        self.db.refresh(report)

        logger.info(
            f"Created crowd report for address {address_id}: "
            f"trash={trash_day}, recycling={recycling_day}, green={green_day}"
        )
        return report

    def get_by_address_id(self, address_id: int) -> List[CrowdReport]:
        """
        Get all reports for a given address.

        Args:
            address_id: Address ID

        Returns:
            List of CrowdReport objects
        """
        return (
            self.db.query(CrowdReport)
            .filter(CrowdReport.address_id == address_id)
            .order_by(CrowdReport.created_at.desc())
            .all()
        )

    def count(self) -> int:
        """
        Get total count of reports.

        Returns:
            Total number of reports
        """
        return self.db.query(CrowdReport).count()


class CrowdConsensusRepository:
    """Repository for CrowdConsensus model operations."""

    def __init__(self, db: Session):
        """
        Initialize the repository.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db

    def get_by_address_id(self, address_id: int) -> Optional[CrowdConsensus]:
        """
        Get consensus for a given address.

        Args:
            address_id: Address ID

        Returns:
            CrowdConsensus object or None
        """
        return (
            self.db.query(CrowdConsensus)
            .filter(CrowdConsensus.address_id == address_id)
            .first()
        )

    def update_or_create(
        self,
        address_id: int,
        consensus_trash_day: Optional[str],
        consensus_recycling_day: Optional[str],
        consensus_green_day: Optional[str],
        total_reports: int,
        trash_agreement_ratio: float,
        recycling_agreement_ratio: float,
        green_agreement_ratio: float,
        is_verified: bool,
    ) -> CrowdConsensus:
        """
        Update existing consensus or create new one.

        Args:
            address_id: Address ID
            consensus_trash_day: Consensus trash day
            consensus_recycling_day: Consensus recycling day
            consensus_green_day: Consensus green waste day
            total_reports: Total number of reports
            trash_agreement_ratio: Agreement ratio for trash
            recycling_agreement_ratio: Agreement ratio for recycling
            green_agreement_ratio: Agreement ratio for green waste
            is_verified: Whether consensus is verified

        Returns:
            Updated or created CrowdConsensus object
        """
        consensus = self.get_by_address_id(address_id)

        if consensus:
            # Update existing
            consensus.consensus_trash_day = consensus_trash_day
            consensus.consensus_recycling_day = consensus_recycling_day
            consensus.consensus_green_day = consensus_green_day
            consensus.total_reports = total_reports
            consensus.trash_agreement_ratio = trash_agreement_ratio
            consensus.recycling_agreement_ratio = recycling_agreement_ratio
            consensus.green_agreement_ratio = green_agreement_ratio
            consensus.is_verified = is_verified
        else:
            # Create new
            consensus = CrowdConsensus(
                address_id=address_id,
                consensus_trash_day=consensus_trash_day,
                consensus_recycling_day=consensus_recycling_day,
                consensus_green_day=consensus_green_day,
                total_reports=total_reports,
                trash_agreement_ratio=trash_agreement_ratio,
                recycling_agreement_ratio=recycling_agreement_ratio,
                green_agreement_ratio=green_agreement_ratio,
                is_verified=is_verified,
            )
            self.db.add(consensus)

        self.db.commit()
        self.db.refresh(consensus)

        logger.info(
            f"Updated consensus for address {address_id}: "
            f"verified={is_verified}, reports={total_reports}"
        )
        return consensus

    def delete_by_address_id(self, address_id: int) -> bool:
        """
        Delete consensus for an address.

        Args:
            address_id: Address ID

        Returns:
            True if deleted, False if not found
        """
        consensus = self.get_by_address_id(address_id)
        if consensus:
            self.db.delete(consensus)
            self.db.commit()
            return True
        return False

    def count(self) -> int:
        """
        Get total count of consensus records.

        Returns:
            Total number of consensus records
        """
        return self.db.query(CrowdConsensus).count()

    def count_verified(self) -> int:
        """
        Get count of verified consensus records.

        Returns:
            Number of verified consensus records
        """
        return (
            self.db.query(CrowdConsensus)
            .filter(CrowdConsensus.is_verified == True)
            .count()
        )


class MetricsRepository:
    """Repository for RequestMetrics model operations."""

    def __init__(self, db: Session):
        """
        Initialize the repository.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db

    def create(
        self,
        endpoint: str,
        method: str,
        status_code: int,
        response_time_ms: float,
        city: Optional[str] = None,
        error_message: Optional[str] = None,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> RequestMetrics:
        """
        Create a new request metrics record.

        Args:
            endpoint: API endpoint
            method: HTTP method
            status_code: HTTP status code
            response_time_ms: Response time in milliseconds
            city: City from request
            error_message: Error message if applicable
            user_agent: User agent string
            ip_address: Client IP address

        Returns:
            Created RequestMetrics object
        """
        metric = RequestMetrics(
            endpoint=endpoint,
            method=method,
            status_code=status_code,
            response_time_ms=response_time_ms,
            city=city,
            error_message=error_message,
            user_agent=user_agent,
            ip_address=ip_address,
        )
        self.db.add(metric)
        self.db.commit()
        self.db.refresh(metric)

        return metric

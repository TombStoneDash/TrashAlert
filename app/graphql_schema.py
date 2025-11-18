"""GraphQL schema for TrashAlert API using Strawberry."""
import strawberry
from typing import Optional, List
from datetime import datetime
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import Address, City, PickupZone, Schedule, CrowdConsensus, CrowdReport


def get_db():
    """Get database session for GraphQL resolvers."""
    db = SessionLocal()
    try:
        return db
    finally:
        pass  # Will be closed by caller


# ============================================================================
# GraphQL Types
# ============================================================================

@strawberry.type
class CityType:
    """GraphQL type for City."""
    id: int
    slug: str
    name: str
    state: Optional[str]
    county: Optional[str]
    region: Optional[str]
    timezone: str
    enabled: bool
    created_at: datetime

    @strawberry.field
    def addresses(self, info, limit: Optional[int] = 100) -> List['AddressType']:
        """Get all addresses in this city."""
        db = info.context["db"]
        # Match by slug
        addresses = db.query(Address).filter(
            Address.city_id == self.slug
        ).limit(limit).all()

        return [
            AddressType(
                id=a.id,
                normalized_address=a.normalized_address,
                house_number=a.house_number,
                street=a.street,
                city_name=a.city_name,
                city_id=a.city_id,
                state=a.state,
                zip_code=a.zip_code,
                lat=a.lat,
                lon=a.lon,
                official_trash_day=a.official_trash_day,
                official_recycling_day=a.official_recycling_day,
                official_green_day=a.official_green_day,
                created_at=a.created_at
            )
            for a in addresses
        ]

    @strawberry.field
    def pickup_zones(self, info, limit: Optional[int] = 100) -> List['PickupZoneType']:
        """Get all pickup zones in this city."""
        db = info.context["db"]
        zones = db.query(PickupZone).filter(
            PickupZone.city_id == self.id
        ).limit(limit).all()

        return [
            PickupZoneType(
                id=z.id,
                city_id=z.city_id,
                name=z.name,
                external_ref=z.external_ref,
                created_at=z.created_at
            )
            for z in zones
        ]


@strawberry.type
class PickupZoneType:
    """GraphQL type for PickupZone."""
    id: int
    city_id: int
    name: str
    external_ref: Optional[str]
    created_at: datetime

    @strawberry.field
    def city(self, info) -> Optional[CityType]:
        """Get the city for this pickup zone."""
        db = info.context["db"]
        city = db.query(City).filter(City.id == self.city_id).first()
        if city:
            return CityType(
                id=city.id,
                slug=city.slug,
                name=city.name,
                state=city.state,
                county=city.county,
                region=city.region,
                timezone=city.timezone,
                enabled=city.enabled,
                created_at=city.created_at
            )
        return None

    @strawberry.field
    def schedules(self, info, limit: Optional[int] = 100) -> List['ScheduleType']:
        """Get all schedules for this pickup zone."""
        db = info.context["db"]
        schedules = db.query(Schedule).filter(
            Schedule.pickup_zone_id == self.id
        ).limit(limit).all()

        return [
            ScheduleType(
                id=s.id,
                city_id=s.city_id,
                pickup_zone_id=s.pickup_zone_id,
                trash_day_of_week=s.trash_day_of_week,
                recycling_day_of_week=s.recycling_day_of_week,
                green_day_of_week=s.green_day_of_week,
                source=s.source,
                created_at=s.created_at
            )
            for s in schedules
        ]


@strawberry.type
class ScheduleType:
    """GraphQL type for Schedule."""
    id: int
    city_id: int
    pickup_zone_id: Optional[int]
    trash_day_of_week: Optional[str]
    recycling_day_of_week: Optional[str]
    green_day_of_week: Optional[str]
    source: str
    created_at: datetime

    @strawberry.field
    def city(self, info) -> Optional[CityType]:
        """Get the city for this schedule."""
        db = info.context["db"]
        city = db.query(City).filter(City.id == self.city_id).first()
        if city:
            return CityType(
                id=city.id,
                slug=city.slug,
                name=city.name,
                state=city.state,
                county=city.county,
                region=city.region,
                timezone=city.timezone,
                enabled=city.enabled,
                created_at=city.created_at
            )
        return None

    @strawberry.field
    def pickup_zone(self, info) -> Optional[PickupZoneType]:
        """Get the pickup zone for this schedule."""
        if not self.pickup_zone_id:
            return None
        db = info.context["db"]
        zone = db.query(PickupZone).filter(PickupZone.id == self.pickup_zone_id).first()
        if zone:
            return PickupZoneType(
                id=zone.id,
                city_id=zone.city_id,
                name=zone.name,
                external_ref=zone.external_ref,
                created_at=zone.created_at
            )
        return None


@strawberry.type
class CrowdConsensusType:
    """GraphQL type for CrowdConsensus."""
    id: int
    address_id: int
    consensus_trash_day: Optional[str]
    consensus_recycling_day: Optional[str]
    consensus_green_day: Optional[str]
    total_reports: int
    trash_agreement_ratio: float
    recycling_agreement_ratio: float
    green_agreement_ratio: float
    is_verified: bool
    created_at: datetime
    updated_at: Optional[datetime]


@strawberry.type
class CrowdReportType:
    """GraphQL type for CrowdReport."""
    id: int
    address_id: int
    trash_day: Optional[str]
    recycling_day: Optional[str]
    green_day: Optional[str]
    user_hash: Optional[str]
    created_at: datetime


@strawberry.type
class AddressType:
    """GraphQL type for Address."""
    id: int
    normalized_address: str
    house_number: Optional[str]
    street: Optional[str]
    city_id: Optional[str]
    city_name: Optional[str]
    state: Optional[str]
    zip_code: Optional[str]
    lat: Optional[float]
    lon: Optional[float]
    official_trash_day: Optional[str]
    official_recycling_day: Optional[str]
    official_green_day: Optional[str]
    created_at: datetime

    @strawberry.field
    def consensus(self, info) -> Optional[CrowdConsensusType]:
        """Get crowd consensus for this address."""
        db = info.context["db"]
        consensus = db.query(CrowdConsensus).filter(
            CrowdConsensus.address_id == self.id
        ).first()
        if consensus:
            return CrowdConsensusType(
                id=consensus.id,
                address_id=consensus.address_id,
                consensus_trash_day=consensus.consensus_trash_day,
                consensus_recycling_day=consensus.consensus_recycling_day,
                consensus_green_day=consensus.consensus_green_day,
                total_reports=consensus.total_reports,
                trash_agreement_ratio=consensus.trash_agreement_ratio,
                recycling_agreement_ratio=consensus.recycling_agreement_ratio,
                green_agreement_ratio=consensus.green_agreement_ratio,
                is_verified=consensus.is_verified,
                created_at=consensus.created_at,
                updated_at=consensus.updated_at
            )
        return None

    @strawberry.field
    def reports(self, info) -> List[CrowdReportType]:
        """Get all crowd reports for this address."""
        db = info.context["db"]
        reports = db.query(CrowdReport).filter(
            CrowdReport.address_id == self.id
        ).all()
        return [
            CrowdReportType(
                id=r.id,
                address_id=r.address_id,
                trash_day=r.trash_day,
                recycling_day=r.recycling_day,
                green_day=r.green_day,
                user_hash=r.user_hash,
                created_at=r.created_at
            )
            for r in reports
        ]


# ============================================================================
# Query Root
# ============================================================================

@strawberry.type
class Query:
    """Root query type."""

    @strawberry.field
    def cities(
        self,
        info,
        enabled: Optional[bool] = None,
        state: Optional[str] = None,
        limit: Optional[int] = 100
    ) -> List[CityType]:
        """
        Get all cities with optional filtering.

        Args:
            enabled: Filter by enabled status
            state: Filter by state
            limit: Maximum number of results (default 100)
        """
        db = info.context["db"]
        from sqlalchemy import inspect

        # Disable lazy loading for this query
        query = db.query(City)

        if enabled is not None:
            query = query.filter(City.enabled == enabled)
        if state:
            query = query.filter(City.state == state)

        query = query.limit(limit)

        # Get results with values only (no ORM relationships)
        cities = query.all()

        return [
            CityType(
                id=c.id,
                slug=c.slug,
                name=c.name,
                state=c.state,
                county=c.county,
                region=c.region,
                timezone=c.timezone if c.timezone else "America/Los_Angeles",
                enabled=c.enabled,
                created_at=c.created_at
            )
            for c in cities
        ]

    @strawberry.field
    def city(self, info, id: Optional[int] = None, slug: Optional[str] = None) -> Optional[CityType]:
        """
        Get a specific city by ID or slug.

        Args:
            id: City ID
            slug: City slug
        """
        db = info.context["db"]

        if id:
            city = db.query(City).filter(City.id == id).first()
        elif slug:
            city = db.query(City).filter(City.slug == slug).first()
        else:
            return None

        if city:
            return CityType(
                id=city.id,
                slug=city.slug,
                name=city.name,
                state=city.state,
                county=city.county,
                region=city.region,
                timezone=city.timezone,
                enabled=city.enabled,
                created_at=city.created_at
            )
        return None

    @strawberry.field
    def addresses(
        self,
        info,
        city_id: Optional[str] = None,
        state: Optional[str] = None,
        zip_code: Optional[str] = None,
        street: Optional[str] = None,
        limit: Optional[int] = 100
    ) -> List[AddressType]:
        """
        Get addresses with optional filtering.

        Args:
            city_id: Filter by city ID
            state: Filter by state
            zip_code: Filter by zip code
            street: Filter by street name (partial match)
            limit: Maximum number of results (default 100)
        """
        db = info.context["db"]
        query = db.query(Address)

        if city_id:
            query = query.filter(Address.city_id == city_id)
        if state:
            query = query.filter(Address.state == state)
        if zip_code:
            query = query.filter(Address.zip_code == zip_code)
        if street:
            query = query.filter(Address.street.ilike(f"%{street}%"))

        query = query.limit(limit)
        addresses = query.all()

        return [
            AddressType(
                id=a.id,
                normalized_address=a.normalized_address,
                house_number=a.house_number,
                street=a.street,
                city_name=a.city_name,
                city_id=a.city_id,
                state=a.state,
                zip_code=a.zip_code,
                lat=a.lat,
                lon=a.lon,
                official_trash_day=a.official_trash_day,
                official_recycling_day=a.official_recycling_day,
                official_green_day=a.official_green_day,
                created_at=a.created_at
            )
            for a in addresses
        ]

    @strawberry.field
    def address(self, info, id: int) -> Optional[AddressType]:
        """
        Get a specific address by ID.

        Args:
            id: Address ID
        """
        db = info.context["db"]
        address = db.query(Address).filter(Address.id == id).first()

        if address:
            return AddressType(
                id=address.id,
                normalized_address=address.normalized_address,
                house_number=address.house_number,
                street=address.street,
                city=address.city,
                city_id=address.city_id,
                state=address.state,
                zip_code=address.zip_code,
                lat=address.lat,
                lon=address.lon,
                official_trash_day=address.official_trash_day,
                official_recycling_day=address.official_recycling_day,
                official_green_day=address.official_green_day,
                created_at=address.created_at
            )
        return None

    @strawberry.field
    def pickup_zones(
        self,
        info,
        city_id: Optional[int] = None,
        limit: Optional[int] = 100
    ) -> List[PickupZoneType]:
        """
        Get pickup zones with optional filtering.

        Args:
            city_id: Filter by city ID
            limit: Maximum number of results (default 100)
        """
        db = info.context["db"]
        query = db.query(PickupZone)

        if city_id:
            query = query.filter(PickupZone.city_id == city_id)

        query = query.limit(limit)
        zones = query.all()

        return [
            PickupZoneType(
                id=z.id,
                city_id=z.city_id,
                name=z.name,
                external_ref=z.external_ref,
                created_at=z.created_at
            )
            for z in zones
        ]

    @strawberry.field
    def pickup_zone(self, info, id: int) -> Optional[PickupZoneType]:
        """
        Get a specific pickup zone by ID.

        Args:
            id: Pickup zone ID
        """
        db = info.context["db"]
        zone = db.query(PickupZone).filter(PickupZone.id == id).first()

        if zone:
            return PickupZoneType(
                id=zone.id,
                city_id=zone.city_id,
                name=zone.name,
                external_ref=zone.external_ref,
                created_at=zone.created_at
            )
        return None

    @strawberry.field
    def schedules(
        self,
        info,
        city_id: Optional[int] = None,
        pickup_zone_id: Optional[int] = None,
        limit: Optional[int] = 100
    ) -> List[ScheduleType]:
        """
        Get schedules with optional filtering.

        Args:
            city_id: Filter by city ID
            pickup_zone_id: Filter by pickup zone ID
            limit: Maximum number of results (default 100)
        """
        db = info.context["db"]
        query = db.query(Schedule)

        if city_id:
            query = query.filter(Schedule.city_id == city_id)
        if pickup_zone_id:
            query = query.filter(Schedule.pickup_zone_id == pickup_zone_id)

        query = query.limit(limit)
        schedules = query.all()

        return [
            ScheduleType(
                id=s.id,
                city_id=s.city_id,
                pickup_zone_id=s.pickup_zone_id,
                trash_day_of_week=s.trash_day_of_week,
                recycling_day_of_week=s.recycling_day_of_week,
                green_day_of_week=s.green_day_of_week,
                source=s.source,
                created_at=s.created_at
            )
            for s in schedules
        ]

    @strawberry.field
    def schedule(self, info, id: int) -> Optional[ScheduleType]:
        """
        Get a specific schedule by ID.

        Args:
            id: Schedule ID
        """
        db = info.context["db"]
        schedule = db.query(Schedule).filter(Schedule.id == id).first()

        if schedule:
            return ScheduleType(
                id=schedule.id,
                city_id=schedule.city_id,
                pickup_zone_id=schedule.pickup_zone_id,
                trash_day_of_week=schedule.trash_day_of_week,
                recycling_day_of_week=schedule.recycling_day_of_week,
                green_day_of_week=schedule.green_day_of_week,
                source=schedule.source,
                created_at=schedule.created_at
            )
        return None


# ============================================================================
# Schema
# ============================================================================

schema = strawberry.Schema(query=Query)

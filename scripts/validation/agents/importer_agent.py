"""
Importer Agent for the multi-agent data validation pipeline.

This agent is responsible for loading schedule data from the database
and preparing it for validation.
"""

from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session, joinedload
from datetime import datetime

from .base_agent import (
    BaseAgent, ValidationIssue, IssueType, IssueSeverity, AgentStatus
)
from app.models import (
    Address, Schedule, PickupZone, City, AddressPickupInfo,
    ScheduleException
)


class ImporterAgent(BaseAgent):
    """
    Agent responsible for importing schedule data for validation.

    This agent loads data from the database and prepares it for the
    validation pipeline. It can import all data or filter by specific
    criteria (city, date range, etc.).
    """

    @property
    def agent_name(self) -> str:
        return "ImporterAgent"

    def _execute(self, context: Dict[str, Any]) -> None:
        """
        Import schedule data from the database.

        Expected context keys:
            - db_session: SQLAlchemy database session
            - city_id: (Optional) Filter by specific city
            - limit: (Optional) Limit number of records
            - include_exceptions: (Optional) Include schedule exceptions

        Sets in context:
            - addresses: List of Address objects
            - schedules: List of Schedule objects
            - pickup_zones: List of PickupZone objects
            - cities: List of City objects
            - schedule_exceptions: List of ScheduleException objects
        """
        db_session: Session = context.get("db_session")
        if not db_session:
            raise ValueError("Database session required in context")

        city_id = context.get("city_id")
        limit = context.get("limit")
        include_exceptions = context.get("include_exceptions", True)

        self.logger.info(
            f"Importing data - City ID: {city_id}, Limit: {limit}, "
            f"Exceptions: {include_exceptions}"
        )

        # Import cities
        cities = self._import_cities(db_session, city_id)
        context["cities"] = cities
        self._update_metadata("cities_count", len(cities))

        # Import pickup zones
        pickup_zones = self._import_pickup_zones(db_session, city_id)
        context["pickup_zones"] = pickup_zones
        self._update_metadata("pickup_zones_count", len(pickup_zones))

        # Import schedules
        schedules = self._import_schedules(db_session, city_id, limit)
        context["schedules"] = schedules
        self._update_metadata("schedules_count", len(schedules))

        # Import addresses
        addresses = self._import_addresses(db_session, city_id, limit)
        context["addresses"] = addresses
        self._update_metadata("addresses_count", len(addresses))

        # Import schedule exceptions if requested
        if include_exceptions:
            exceptions = self._import_schedule_exceptions(db_session, city_id)
            context["schedule_exceptions"] = exceptions
            self._update_metadata("exceptions_count", len(exceptions))

        # Import address pickup info
        address_pickup_info = self._import_address_pickup_info(db_session, city_id, limit)
        context["address_pickup_info"] = address_pickup_info
        self._update_metadata("address_pickup_info_count", len(address_pickup_info))

        # Validate that we imported some data
        total_records = (
            len(cities) + len(pickup_zones) + len(schedules) + len(addresses)
        )

        if total_records == 0:
            self._add_issue(ValidationIssue(
                issue_type=IssueType.MISSING_DATA,
                severity=IssueSeverity.HIGH,
                message="No data imported from database",
                entity_type="Import",
                correctable=False,
                metadata={"city_id": city_id, "limit": limit}
            ))
            self._result.status = AgentStatus.FAILED
        else:
            self.logger.info(f"Successfully imported {total_records} total records")

    def _import_cities(
        self, db_session: Session, city_id: Optional[int] = None
    ) -> List[City]:
        """Import city data."""
        query = db_session.query(City)

        if city_id:
            query = query.filter(City.id == city_id)

        cities = query.all()
        self.logger.debug(f"Imported {len(cities)} cities")
        return cities

    def _import_pickup_zones(
        self, db_session: Session, city_id: Optional[int] = None
    ) -> List[PickupZone]:
        """Import pickup zone data."""
        query = db_session.query(PickupZone).options(
            joinedload(PickupZone.city)
        )

        if city_id:
            query = query.filter(PickupZone.city_id == city_id)

        zones = query.all()
        self.logger.debug(f"Imported {len(zones)} pickup zones")
        return zones

    def _import_schedules(
        self,
        db_session: Session,
        city_id: Optional[int] = None,
        limit: Optional[int] = None
    ) -> List[Schedule]:
        """Import schedule data."""
        query = db_session.query(Schedule).options(
            joinedload(Schedule.city),
            joinedload(Schedule.pickup_zone)
        )

        if city_id:
            query = query.filter(Schedule.city_id == city_id)

        if limit:
            query = query.limit(limit)

        schedules = query.all()
        self.logger.debug(f"Imported {len(schedules)} schedules")
        return schedules

    def _import_addresses(
        self,
        db_session: Session,
        city_id: Optional[int] = None,
        limit: Optional[int] = None
    ) -> List[Address]:
        """Import address data."""
        query = db_session.query(Address).options(
            joinedload(Address.city)
        )

        if city_id:
            query = query.filter(Address.city_id == city_id)

        if limit:
            query = query.limit(limit)

        addresses = query.all()
        self.logger.debug(f"Imported {len(addresses)} addresses")
        return addresses

    def _import_schedule_exceptions(
        self,
        db_session: Session,
        city_id: Optional[int] = None
    ) -> List[ScheduleException]:
        """Import schedule exception data."""
        query = db_session.query(ScheduleException).options(
            joinedload(ScheduleException.city)
        )

        if city_id:
            query = query.filter(ScheduleException.city_id == city_id)

        # Only get future and recent exceptions (last 30 days)
        from datetime import timedelta
        cutoff_date = datetime.now().date() - timedelta(days=30)
        query = query.filter(ScheduleException.exception_date >= cutoff_date)

        exceptions = query.all()
        self.logger.debug(f"Imported {len(exceptions)} schedule exceptions")
        return exceptions

    def _import_address_pickup_info(
        self,
        db_session: Session,
        city_id: Optional[int] = None,
        limit: Optional[int] = None
    ) -> List[AddressPickupInfo]:
        """Import address pickup info data."""
        query = db_session.query(AddressPickupInfo).options(
            joinedload(AddressPickupInfo.address),
            joinedload(AddressPickupInfo.pickup_zone)
        )

        if city_id:
            # Filter by city through address relationship
            query = query.join(Address).filter(Address.city_id == city_id)

        if limit:
            query = query.limit(limit)

        pickup_info = query.all()
        self.logger.debug(f"Imported {len(pickup_info)} address pickup info records")
        return pickup_info

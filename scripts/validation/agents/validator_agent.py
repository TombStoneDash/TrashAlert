"""
Validator Agent for the multi-agent data validation pipeline.

This agent is responsible for detecting schedule inconsistencies and
data quality issues in the imported data.
"""

from typing import Dict, Any, List, Optional, Set
from datetime import datetime, date

from .base_agent import (
    BaseAgent, ValidationIssue, IssueType, IssueSeverity
)
from app.models import Address, Schedule, PickupZone, ScheduleException


class ValidatorAgent(BaseAgent):
    """
    Agent responsible for validating schedule data and detecting inconsistencies.

    This agent performs comprehensive validation including:
    - Schedule consistency checks
    - Missing data detection
    - Invalid format validation
    - Business rule validation
    - Cross-reference validation
    """

    VALID_DAYS = {0, 1, 2, 3, 4, 5, 6}  # 0=Monday, 6=Sunday
    VALID_DAY_NAMES = {
        'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'
    }

    @property
    def agent_name(self) -> str:
        return "ValidatorAgent"

    def _execute(self, context: Dict[str, Any]) -> None:
        """
        Validate schedule data and detect inconsistencies.

        Expected context keys:
            - addresses: List of Address objects
            - schedules: List of Schedule objects
            - pickup_zones: List of PickupZone objects
            - cities: List of City objects
            - schedule_exceptions: (Optional) List of ScheduleException objects
            - address_pickup_info: List of AddressPickupInfo objects

        Sets in context:
            - validation_issues: List of all detected issues
        """
        self.logger.info("Starting validation")

        addresses = context.get("addresses", [])
        schedules = context.get("schedules", [])
        pickup_zones = context.get("pickup_zones", [])
        address_pickup_info = context.get("address_pickup_info", [])
        schedule_exceptions = context.get("schedule_exceptions", [])

        # Run validation checks
        self._validate_schedules(schedules)
        self._validate_addresses(addresses)
        self._validate_pickup_zones(pickup_zones)
        self._validate_address_schedule_consistency(addresses, schedules, pickup_zones)
        self._validate_address_pickup_info(address_pickup_info)
        self._validate_schedule_exceptions(schedule_exceptions)

        # Store issues in context for other agents
        context["validation_issues"] = self._result.issues_detected

        self.logger.info(
            f"Validation complete: {len(self._result.issues_detected)} issues found"
        )

    def _validate_schedules(self, schedules: List[Schedule]) -> None:
        """Validate schedule records."""
        self.logger.debug(f"Validating {len(schedules)} schedules")

        for schedule in schedules:
            # Check for missing city reference
            if not schedule.city_id:
                self._add_issue(ValidationIssue(
                    issue_type=IssueType.MISSING_DATA,
                    severity=IssueSeverity.HIGH,
                    message="Schedule missing city_id",
                    entity_type="Schedule",
                    entity_id=schedule.id,
                    field_name="city_id",
                    current_value=None
                ))

            # Check for missing pickup zone reference
            if not schedule.pickup_zone_id:
                self._add_issue(ValidationIssue(
                    issue_type=IssueType.MISSING_DATA,
                    severity=IssueSeverity.MEDIUM,
                    message="Schedule missing pickup_zone_id",
                    entity_type="Schedule",
                    entity_id=schedule.id,
                    field_name="pickup_zone_id",
                    current_value=None
                ))

            # Validate day of week values
            self._validate_day_of_week(schedule, "trash_day_of_week")
            self._validate_day_of_week(schedule, "recycling_day_of_week")
            self._validate_day_of_week(schedule, "green_day_of_week")

            # Check for schedules with no pickup days defined
            if (not schedule.trash_day_of_week and
                not schedule.recycling_day_of_week and
                not schedule.green_day_of_week):
                self._add_issue(ValidationIssue(
                    issue_type=IssueType.MISSING_DATA,
                    severity=IssueSeverity.HIGH,
                    message="Schedule has no pickup days defined",
                    entity_type="Schedule",
                    entity_id=schedule.id,
                    field_name="pickup_days",
                    current_value=None
                ))

            # Check for inconsistent schedule patterns
            self._check_schedule_consistency(schedule)

    def _validate_day_of_week(
        self, schedule: Schedule, field_name: str
    ) -> None:
        """Validate day of week field."""
        value = getattr(schedule, field_name, None)

        if value is None:
            return  # Null is acceptable (service not offered)

        # Check if it's a valid integer day (0-6)
        if isinstance(value, int):
            if value not in self.VALID_DAYS:
                self._add_issue(ValidationIssue(
                    issue_type=IssueType.INVALID_FORMAT,
                    severity=IssueSeverity.HIGH,
                    message=f"Invalid day of week value: {value} (must be 0-6)",
                    entity_type="Schedule",
                    entity_id=schedule.id,
                    field_name=field_name,
                    current_value=value,
                    expected_value="0-6 (0=Monday, 6=Sunday)"
                ))
        # Check if it's a valid day name string
        elif isinstance(value, str):
            if value.lower() not in self.VALID_DAY_NAMES:
                self._add_issue(ValidationIssue(
                    issue_type=IssueType.INVALID_FORMAT,
                    severity=IssueSeverity.HIGH,
                    message=f"Invalid day name: {value}",
                    entity_type="Schedule",
                    entity_id=schedule.id,
                    field_name=field_name,
                    current_value=value,
                    expected_value="Valid day name (Monday-Sunday)"
                ))
        else:
            self._add_issue(ValidationIssue(
                issue_type=IssueType.INVALID_FORMAT,
                severity=IssueSeverity.HIGH,
                message=f"Invalid day type: {type(value).__name__}",
                entity_type="Schedule",
                entity_id=schedule.id,
                field_name=field_name,
                current_value=str(value),
                expected_value="Integer (0-6) or day name string"
            ))

    def _check_schedule_consistency(self, schedule: Schedule) -> None:
        """Check for logical inconsistencies in schedule."""
        # Check if trash and recycling are on the same day (unusual)
        if (schedule.trash_day_of_week is not None and
            schedule.recycling_day_of_week is not None and
            schedule.trash_day_of_week == schedule.recycling_day_of_week):
            self._add_issue(ValidationIssue(
                issue_type=IssueType.INCONSISTENT_SCHEDULE,
                severity=IssueSeverity.LOW,
                message="Trash and recycling scheduled on the same day",
                entity_type="Schedule",
                entity_id=schedule.id,
                field_name="schedule_consistency",
                metadata={
                    "trash_day": schedule.trash_day_of_week,
                    "recycling_day": schedule.recycling_day_of_week
                }
            ))

    def _validate_addresses(self, addresses: List[Address]) -> None:
        """Validate address records."""
        self.logger.debug(f"Validating {len(addresses)} addresses")

        for address in addresses:
            # Check for missing required fields
            if not address.street_number:
                self._add_issue(ValidationIssue(
                    issue_type=IssueType.MISSING_DATA,
                    severity=IssueSeverity.MEDIUM,
                    message="Address missing street_number",
                    entity_type="Address",
                    entity_id=address.id,
                    field_name="street_number",
                    current_value=None
                ))

            if not address.street_name:
                self._add_issue(ValidationIssue(
                    issue_type=IssueType.MISSING_DATA,
                    severity=IssueSeverity.HIGH,
                    message="Address missing street_name",
                    entity_type="Address",
                    entity_id=address.id,
                    field_name="street_name",
                    current_value=None
                ))

            if not address.city_id:
                self._add_issue(ValidationIssue(
                    issue_type=IssueType.MISSING_DATA,
                    severity=IssueSeverity.CRITICAL,
                    message="Address missing city_id",
                    entity_type="Address",
                    entity_id=address.id,
                    field_name="city_id",
                    current_value=None
                ))

            # Validate coordinates if present
            if address.latitude is not None or address.longitude is not None:
                if address.latitude is None or address.longitude is None:
                    self._add_issue(ValidationIssue(
                        issue_type=IssueType.INCONSISTENT_SCHEDULE,
                        severity=IssueSeverity.MEDIUM,
                        message="Incomplete coordinates (lat or lon missing)",
                        entity_type="Address",
                        entity_id=address.id,
                        field_name="coordinates",
                        metadata={
                            "latitude": address.latitude,
                            "longitude": address.longitude
                        }
                    ))
                else:
                    # Validate coordinate ranges
                    if not (-90 <= address.latitude <= 90):
                        self._add_issue(ValidationIssue(
                            issue_type=IssueType.INVALID_FORMAT,
                            severity=IssueSeverity.HIGH,
                            message=f"Invalid latitude: {address.latitude}",
                            entity_type="Address",
                            entity_id=address.id,
                            field_name="latitude",
                            current_value=address.latitude,
                            expected_value="-90 to 90"
                        ))

                    if not (-180 <= address.longitude <= 180):
                        self._add_issue(ValidationIssue(
                            issue_type=IssueType.INVALID_FORMAT,
                            severity=IssueSeverity.HIGH,
                            message=f"Invalid longitude: {address.longitude}",
                            entity_type="Address",
                            entity_id=address.id,
                            field_name="longitude",
                            current_value=address.longitude,
                            expected_value="-180 to 180"
                        ))

    def _validate_pickup_zones(self, pickup_zones: List[PickupZone]) -> None:
        """Validate pickup zone records."""
        self.logger.debug(f"Validating {len(pickup_zones)} pickup zones")

        zone_names: Dict[int, Set[str]] = {}  # city_id -> set of zone names

        for zone in pickup_zones:
            # Check for missing city reference
            if not zone.city_id:
                self._add_issue(ValidationIssue(
                    issue_type=IssueType.MISSING_DATA,
                    severity=IssueSeverity.HIGH,
                    message="PickupZone missing city_id",
                    entity_type="PickupZone",
                    entity_id=zone.id,
                    field_name="city_id",
                    current_value=None
                ))

            # Check for missing zone name
            if not zone.zone_name:
                self._add_issue(ValidationIssue(
                    issue_type=IssueType.MISSING_DATA,
                    severity=IssueSeverity.MEDIUM,
                    message="PickupZone missing zone_name",
                    entity_type="PickupZone",
                    entity_id=zone.id,
                    field_name="zone_name",
                    current_value=None
                ))
            else:
                # Check for duplicate zone names within the same city
                if zone.city_id:
                    if zone.city_id not in zone_names:
                        zone_names[zone.city_id] = set()

                    if zone.zone_name in zone_names[zone.city_id]:
                        self._add_issue(ValidationIssue(
                            issue_type=IssueType.DUPLICATE_DATA,
                            severity=IssueSeverity.MEDIUM,
                            message=f"Duplicate zone name: {zone.zone_name}",
                            entity_type="PickupZone",
                            entity_id=zone.id,
                            field_name="zone_name",
                            current_value=zone.zone_name,
                            metadata={"city_id": zone.city_id}
                        ))
                    else:
                        zone_names[zone.city_id].add(zone.zone_name)

    def _validate_address_schedule_consistency(
        self,
        addresses: List[Address],
        schedules: List[Schedule],
        pickup_zones: List[PickupZone]
    ) -> None:
        """Validate consistency between addresses, schedules, and pickup zones."""
        self.logger.debug("Validating address-schedule consistency")

        # Create lookup dictionaries
        schedule_by_zone: Dict[int, Schedule] = {
            s.pickup_zone_id: s for s in schedules if s.pickup_zone_id
        }
        zone_by_id: Dict[int, PickupZone] = {z.id: z for z in pickup_zones}

        for address in addresses:
            # Skip addresses without official pickup days
            if not any([
                address.official_trash_day,
                address.official_recycling_day,
                address.official_green_day
            ]):
                continue

            # Check if address has a pickup zone reference
            # (We'll check through the address's relationships)
            if hasattr(address, 'pickup_zone_id') and address.pickup_zone_id:
                zone = zone_by_id.get(address.pickup_zone_id)
                if not zone:
                    self._add_issue(ValidationIssue(
                        issue_type=IssueType.REFERENCE_ERROR,
                        severity=IssueSeverity.HIGH,
                        message=f"Address references non-existent pickup zone",
                        entity_type="Address",
                        entity_id=address.id,
                        field_name="pickup_zone_id",
                        current_value=address.pickup_zone_id
                    ))
                else:
                    # Check if pickup zone has a schedule
                    schedule = schedule_by_zone.get(address.pickup_zone_id)
                    if not schedule:
                        self._add_issue(ValidationIssue(
                            issue_type=IssueType.MISSING_DATA,
                            severity=IssueSeverity.MEDIUM,
                            message=f"Pickup zone has no associated schedule",
                            entity_type="PickupZone",
                            entity_id=zone.id,
                            field_name="schedule",
                            metadata={
                                "address_id": address.id,
                                "zone_name": zone.zone_name
                            }
                        ))

    def _validate_address_pickup_info(
        self, address_pickup_info: List
    ) -> None:
        """Validate address pickup info records."""
        self.logger.debug(f"Validating {len(address_pickup_info)} address pickup info records")

        for info in address_pickup_info:
            # Check for missing address reference
            if not info.address_id:
                self._add_issue(ValidationIssue(
                    issue_type=IssueType.MISSING_DATA,
                    severity=IssueSeverity.CRITICAL,
                    message="AddressPickupInfo missing address_id",
                    entity_type="AddressPickupInfo",
                    entity_id=info.id,
                    field_name="address_id",
                    current_value=None
                ))

            # Check for missing source
            if not info.source:
                self._add_issue(ValidationIssue(
                    issue_type=IssueType.MISSING_DATA,
                    severity=IssueSeverity.MEDIUM,
                    message="AddressPickupInfo missing source",
                    entity_type="AddressPickupInfo",
                    entity_id=info.id,
                    field_name="source",
                    current_value=None
                ))

            # Validate day of week fields
            for field in ['trash_day_of_week', 'recycling_day_of_week', 'green_day_of_week']:
                value = getattr(info, field, None)
                if value is not None and value not in self.VALID_DAYS:
                    self._add_issue(ValidationIssue(
                        issue_type=IssueType.INVALID_FORMAT,
                        severity=IssueSeverity.HIGH,
                        message=f"Invalid day of week value in {field}: {value}",
                        entity_type="AddressPickupInfo",
                        entity_id=info.id,
                        field_name=field,
                        current_value=value,
                        expected_value="0-6"
                    ))

    def _validate_schedule_exceptions(
        self, schedule_exceptions: List[ScheduleException]
    ) -> None:
        """Validate schedule exception records."""
        if not schedule_exceptions:
            return

        self.logger.debug(f"Validating {len(schedule_exceptions)} schedule exceptions")

        today = date.today()

        for exception in schedule_exceptions:
            # Check for missing required fields
            if not exception.city_id:
                self._add_issue(ValidationIssue(
                    issue_type=IssueType.MISSING_DATA,
                    severity=IssueSeverity.HIGH,
                    message="ScheduleException missing city_id",
                    entity_type="ScheduleException",
                    entity_id=exception.id,
                    field_name="city_id",
                    current_value=None
                ))

            if not exception.exception_date:
                self._add_issue(ValidationIssue(
                    issue_type=IssueType.MISSING_DATA,
                    severity=IssueSeverity.CRITICAL,
                    message="ScheduleException missing exception_date",
                    entity_type="ScheduleException",
                    entity_id=exception.id,
                    field_name="exception_date",
                    current_value=None
                ))

            # Check for past exceptions (might indicate stale data)
            if exception.exception_date and exception.exception_date < today:
                from datetime import timedelta
                if exception.exception_date < today - timedelta(days=30):
                    self._add_issue(ValidationIssue(
                        issue_type=IssueType.DATA_QUALITY,
                        severity=IssueSeverity.LOW,
                        message="Old schedule exception (>30 days past)",
                        entity_type="ScheduleException",
                        entity_id=exception.id,
                        field_name="exception_date",
                        current_value=exception.exception_date.isoformat(),
                        metadata={"cleanup_candidate": True}
                    ))

            # Validate rescheduled date if present
            if exception.rescheduled_date:
                if exception.rescheduled_date < exception.exception_date:
                    self._add_issue(ValidationIssue(
                        issue_type=IssueType.INCONSISTENT_SCHEDULE,
                        severity=IssueSeverity.HIGH,
                        message="Rescheduled date is before exception date",
                        entity_type="ScheduleException",
                        entity_id=exception.id,
                        field_name="rescheduled_date",
                        current_value=exception.rescheduled_date.isoformat(),
                        expected_value=f"After {exception.exception_date.isoformat()}"
                    ))

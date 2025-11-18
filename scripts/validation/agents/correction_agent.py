"""
Correction Agent for the multi-agent data validation pipeline.

This agent is responsible for generating correction actions for detected
validation issues.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime

from .base_agent import (
    BaseAgent, ValidationIssue, CorrectionAction, IssueType, IssueSeverity
)


class CorrectionAgent(BaseAgent):
    """
    Agent responsible for generating correction actions for validation issues.

    This agent analyzes validation issues and proposes corrections that
    can be applied to fix the data. It uses heuristics and business rules
    to determine appropriate fixes.
    """

    # Mapping from day names to day numbers (0=Monday)
    DAY_NAME_TO_NUMBER = {
        'monday': 0,
        'tuesday': 1,
        'wednesday': 2,
        'thursday': 3,
        'friday': 4,
        'saturday': 5,
        'sunday': 6
    }

    @property
    def agent_name(self) -> str:
        return "CorrectionAgent"

    def _execute(self, context: Dict[str, Any]) -> None:
        """
        Generate correction actions for validation issues.

        Expected context keys:
            - validation_issues: List of ValidationIssue objects

        Sets in context:
            - correction_actions: List of CorrectionAction objects
        """
        validation_issues = context.get("validation_issues", [])

        if not validation_issues:
            self.logger.info("No validation issues to correct")
            context["correction_actions"] = []
            return

        self.logger.info(f"Generating corrections for {len(validation_issues)} issues")

        corrections = []
        for issue in validation_issues:
            if not issue.correctable:
                self.logger.debug(f"Skipping non-correctable issue: {issue.message}")
                continue

            correction = self._generate_correction(issue)
            if correction:
                corrections.append(correction)
                self._add_correction(correction, applied=False)

        context["correction_actions"] = corrections

        self.logger.info(
            f"Generated {len(corrections)} correction actions "
            f"for {len(validation_issues)} issues"
        )

        # Update metadata
        self._update_metadata("total_issues", len(validation_issues))
        self._update_metadata("correctable_issues", len(corrections))
        self._update_metadata("non_correctable_issues",
                            len([i for i in validation_issues if not i.correctable]))

    def _generate_correction(self, issue: ValidationIssue) -> Optional[CorrectionAction]:
        """Generate a correction action for a validation issue."""

        # Route to specific correction handlers based on issue type
        if issue.issue_type == IssueType.INVALID_FORMAT:
            return self._correct_invalid_format(issue)
        elif issue.issue_type == IssueType.INCONSISTENT_SCHEDULE:
            return self._correct_inconsistent_schedule(issue)
        elif issue.issue_type == IssueType.MISSING_DATA:
            return self._correct_missing_data(issue)
        elif issue.issue_type == IssueType.DUPLICATE_DATA:
            return self._correct_duplicate_data(issue)
        elif issue.issue_type == IssueType.DATA_QUALITY:
            return self._correct_data_quality(issue)
        elif issue.issue_type == IssueType.REFERENCE_ERROR:
            return self._correct_reference_error(issue)

        self.logger.debug(f"No correction handler for issue type: {issue.issue_type.value}")
        return None

    def _correct_invalid_format(self, issue: ValidationIssue) -> Optional[CorrectionAction]:
        """Generate correction for invalid format issues."""

        # Handle invalid day of week strings (convert to numbers)
        if 'day' in issue.field_name.lower() and isinstance(issue.current_value, str):
            day_name = issue.current_value.lower().strip()
            if day_name in self.DAY_NAME_TO_NUMBER:
                return CorrectionAction(
                    issue=issue,
                    action_type="update",
                    entity_type=issue.entity_type,
                    entity_id=issue.entity_id,
                    changes={
                        issue.field_name: self.DAY_NAME_TO_NUMBER[day_name]
                    }
                )

        # Handle invalid coordinate values (set to None if out of range)
        if issue.field_name in ['latitude', 'longitude']:
            return CorrectionAction(
                issue=issue,
                action_type="update",
                entity_type=issue.entity_type,
                entity_id=issue.entity_id,
                changes={
                    issue.field_name: None,
                    'geocoded': False  # Mark as needing geocoding
                }
            )

        # Handle invalid day numbers (set to None)
        if 'day_of_week' in issue.field_name:
            return CorrectionAction(
                issue=issue,
                action_type="update",
                entity_type=issue.entity_type,
                entity_id=issue.entity_id,
                changes={
                    issue.field_name: None
                }
            )

        return None

    def _correct_inconsistent_schedule(self, issue: ValidationIssue) -> Optional[CorrectionAction]:
        """Generate correction for inconsistent schedule issues."""

        # Handle incomplete coordinates (clear both if one is missing)
        if issue.field_name == "coordinates":
            return CorrectionAction(
                issue=issue,
                action_type="update",
                entity_type=issue.entity_type,
                entity_id=issue.entity_id,
                changes={
                    'latitude': None,
                    'longitude': None,
                    'geocoded': False
                }
            )

        # Handle rescheduled date before exception date
        if issue.field_name == "rescheduled_date":
            # Set rescheduled_date to None to mark for manual review
            return CorrectionAction(
                issue=issue,
                action_type="update",
                entity_type=issue.entity_type,
                entity_id=issue.entity_id,
                changes={
                    'rescheduled_date': None,
                    'needs_review': True
                }
            )

        # Handle trash and recycling on same day (informational only)
        if issue.severity == IssueSeverity.LOW:
            # Don't auto-correct low severity inconsistencies
            return None

        return None

    def _correct_missing_data(self, issue: ValidationIssue) -> Optional[CorrectionAction]:
        """Generate correction for missing data issues."""

        # For critical missing data (like city_id), we can't auto-correct
        if issue.severity == IssueSeverity.CRITICAL:
            self.logger.warning(
                f"Cannot auto-correct critical missing data: {issue.message}"
            )
            return None

        # For schedules with no pickup days, mark for review
        if issue.entity_type == "Schedule" and issue.field_name == "pickup_days":
            return CorrectionAction(
                issue=issue,
                action_type="update",
                entity_type=issue.entity_type,
                entity_id=issue.entity_id,
                changes={
                    'needs_review': True,
                    'review_reason': 'No pickup days defined'
                }
            )

        # For missing zone names, generate a default name
        if issue.entity_type == "PickupZone" and issue.field_name == "zone_name":
            default_name = f"Zone_{issue.entity_id}"
            return CorrectionAction(
                issue=issue,
                action_type="update",
                entity_type=issue.entity_type,
                entity_id=issue.entity_id,
                changes={
                    'zone_name': default_name,
                    'needs_review': True
                }
            )

        return None

    def _correct_duplicate_data(self, issue: ValidationIssue) -> Optional[CorrectionAction]:
        """Generate correction for duplicate data issues."""

        # For duplicate zone names, append the ID to make it unique
        if issue.entity_type == "PickupZone" and issue.field_name == "zone_name":
            new_name = f"{issue.current_value}_{issue.entity_id}"
            return CorrectionAction(
                issue=issue,
                action_type="update",
                entity_type=issue.entity_type,
                entity_id=issue.entity_id,
                changes={
                    'zone_name': new_name
                }
            )

        return None

    def _correct_data_quality(self, issue: ValidationIssue) -> Optional[CorrectionAction]:
        """Generate correction for data quality issues."""

        # Handle old schedule exceptions (mark for deletion)
        if (issue.entity_type == "ScheduleException" and
            issue.metadata.get('cleanup_candidate')):
            return CorrectionAction(
                issue=issue,
                action_type="delete",
                entity_type=issue.entity_type,
                entity_id=issue.entity_id,
                changes={}
            )

        return None

    def _correct_reference_error(self, issue: ValidationIssue) -> Optional[CorrectionAction]:
        """Generate correction for reference errors."""

        # For addresses referencing non-existent pickup zones, clear the reference
        if issue.entity_type == "Address" and issue.field_name == "pickup_zone_id":
            return CorrectionAction(
                issue=issue,
                action_type="update",
                entity_type=issue.entity_type,
                entity_id=issue.entity_id,
                changes={
                    'pickup_zone_id': None,
                    'needs_zone_assignment': True
                }
            )

        return None

    def filter_corrections_by_severity(
        self,
        corrections: List[CorrectionAction],
        min_severity: IssueSeverity
    ) -> List[CorrectionAction]:
        """
        Filter corrections to only include those above a certain severity level.

        Args:
            corrections: List of correction actions
            min_severity: Minimum severity level to include

        Returns:
            Filtered list of correction actions
        """
        severity_order = [
            IssueSeverity.INFO,
            IssueSeverity.LOW,
            IssueSeverity.MEDIUM,
            IssueSeverity.HIGH,
            IssueSeverity.CRITICAL
        ]

        min_level = severity_order.index(min_severity)

        return [
            corr for corr in corrections
            if severity_order.index(corr.issue.severity) >= min_level
        ]

    def group_corrections_by_entity(
        self,
        corrections: List[CorrectionAction]
    ) -> Dict[str, List[CorrectionAction]]:
        """
        Group corrections by entity type for batch processing.

        Args:
            corrections: List of correction actions

        Returns:
            Dictionary mapping entity type to list of corrections
        """
        grouped = {}
        for correction in corrections:
            entity_type = correction.entity_type
            if entity_type not in grouped:
                grouped[entity_type] = []
            grouped[entity_type].append(correction)

        return grouped

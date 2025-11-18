"""
Multi-agent data validation pipeline orchestrator.

This module coordinates the execution of all validation agents in the
proper sequence to validate and repair schedule data.
"""

import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import json

from sqlalchemy.orm import Session

from .agents import (
    ImporterAgent,
    ValidatorAgent,
    CorrectionAgent,
    UpdaterAgent,
    AgentResult,
    AgentStatus,
    ValidationIssue
)


@dataclass
class PipelineConfig:
    """Configuration for the validation pipeline."""
    city_id: Optional[int] = None
    limit: Optional[int] = None
    include_exceptions: bool = True
    dry_run: bool = False
    batch_size: int = 100
    min_severity: Optional[str] = None
    auto_apply_corrections: bool = True
    save_report: bool = True
    report_output_dir: str = "data/validation_reports"


@dataclass
class PipelineResult:
    """Result of pipeline execution."""
    pipeline_name: str
    status: AgentStatus
    agent_results: List[AgentResult] = field(default_factory=list)
    total_issues: int = 0
    total_corrections_proposed: int = 0
    total_corrections_applied: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    error_message: Optional[str] = None
    report_path: Optional[str] = None

    @property
    def duration(self) -> Optional[float]:
        """Calculate duration in seconds."""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary format."""
        return {
            "pipeline_name": self.pipeline_name,
            "status": self.status.value,
            "agent_results": [result.to_dict() for result in self.agent_results],
            "total_issues": self.total_issues,
            "total_corrections_proposed": self.total_corrections_proposed,
            "total_corrections_applied": self.total_corrections_applied,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration": self.duration,
            "error_message": self.error_message,
            "report_path": self.report_path
        }


class ValidationPipeline:
    """
    Multi-agent validation pipeline orchestrator.

    This class coordinates the execution of all validation agents to:
    1. Import schedule data
    2. Validate and detect inconsistencies
    3. Generate correction actions
    4. Apply corrections to the database
    """

    def __init__(self, config: Optional[PipelineConfig] = None):
        """
        Initialize the validation pipeline.

        Args:
            config: Pipeline configuration
        """
        self.config = config or PipelineConfig()
        self.logger = logging.getLogger(__name__)
        self._result: Optional[PipelineResult] = None

    @property
    def result(self) -> Optional[PipelineResult]:
        """Get the result of the last pipeline execution."""
        return self._result

    def run(self, db_session: Session) -> PipelineResult:
        """
        Execute the validation pipeline.

        Args:
            db_session: SQLAlchemy database session

        Returns:
            PipelineResult with execution details
        """
        self.logger.info("=" * 80)
        self.logger.info("Starting Multi-Agent Data Validation Pipeline")
        self.logger.info("=" * 80)

        self._result = PipelineResult(
            pipeline_name="ScheduleValidationPipeline",
            status=AgentStatus.RUNNING,
            start_time=datetime.utcnow()
        )

        # Create execution context shared by all agents
        context: Dict[str, Any] = {
            "db_session": db_session,
            "city_id": self.config.city_id,
            "limit": self.config.limit,
            "include_exceptions": self.config.include_exceptions,
            "dry_run": self.config.dry_run,
            "batch_size": self.config.batch_size
        }

        try:
            # Stage 1: Import data
            self.logger.info("\n" + "=" * 80)
            self.logger.info("STAGE 1: Data Import")
            self.logger.info("=" * 80)
            importer_result = self._run_importer(context)
            self._result.agent_results.append(importer_result)

            if importer_result.status == AgentStatus.FAILED:
                raise RuntimeError(f"Importer failed: {importer_result.error_message}")

            # Stage 2: Validate data
            self.logger.info("\n" + "=" * 80)
            self.logger.info("STAGE 2: Data Validation")
            self.logger.info("=" * 80)
            validator_result = self._run_validator(context)
            self._result.agent_results.append(validator_result)
            self._result.total_issues = len(validator_result.issues_detected)

            if validator_result.status == AgentStatus.FAILED:
                raise RuntimeError(f"Validator failed: {validator_result.error_message}")

            # Stage 3: Generate corrections
            self.logger.info("\n" + "=" * 80)
            self.logger.info("STAGE 3: Correction Generation")
            self.logger.info("=" * 80)
            correction_result = self._run_correction(context)
            self._result.agent_results.append(correction_result)
            self._result.total_corrections_proposed = len(
                correction_result.corrections_proposed
            )

            if correction_result.status == AgentStatus.FAILED:
                raise RuntimeError(f"Correction failed: {correction_result.error_message}")

            # Stage 4: Apply corrections (if enabled)
            if self.config.auto_apply_corrections and correction_result.corrections_proposed:
                self.logger.info("\n" + "=" * 80)
                self.logger.info("STAGE 4: Applying Corrections")
                self.logger.info("=" * 80)
                updater_result = self._run_updater(context)
                self._result.agent_results.append(updater_result)
                self._result.total_corrections_applied = len(
                    updater_result.corrections_applied
                )

                if updater_result.status == AgentStatus.FAILED:
                    self.logger.error(f"Updater failed: {updater_result.error_message}")
                    # Don't fail the whole pipeline if updater fails
            else:
                if not self.config.auto_apply_corrections:
                    self.logger.info("\n" + "=" * 80)
                    self.logger.info("STAGE 4: Skipped (auto_apply_corrections=False)")
                    self.logger.info("=" * 80)
                else:
                    self.logger.info("\n" + "=" * 80)
                    self.logger.info("STAGE 4: Skipped (no corrections to apply)")
                    self.logger.info("=" * 80)

            self._result.status = AgentStatus.SUCCESS

        except Exception as e:
            self.logger.error(f"Pipeline failed: {str(e)}", exc_info=True)
            self._result.status = AgentStatus.FAILED
            self._result.error_message = str(e)

        finally:
            self._result.end_time = datetime.utcnow()

            # Generate report
            if self.config.save_report:
                report_path = self._save_report()
                self._result.report_path = report_path

            # Log summary
            self._log_summary()

        return self._result

    def _run_importer(self, context: Dict[str, Any]) -> AgentResult:
        """Run the Importer agent."""
        importer = ImporterAgent()
        result = importer.run(context)
        return result

    def _run_validator(self, context: Dict[str, Any]) -> AgentResult:
        """Run the Validator agent."""
        validator = ValidatorAgent()
        result = validator.run(context)
        return result

    def _run_correction(self, context: Dict[str, Any]) -> AgentResult:
        """Run the Correction agent."""
        correction = CorrectionAgent()
        result = correction.run(context)
        return result

    def _run_updater(self, context: Dict[str, Any]) -> AgentResult:
        """Run the Updater agent."""
        updater = UpdaterAgent()
        result = updater.run(context)
        return result

    def _save_report(self) -> str:
        """Save validation report to file."""
        try:
            # Create report directory if it doesn't exist
            report_dir = Path(self.config.report_output_dir)
            report_dir.mkdir(parents=True, exist_ok=True)

            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_file = report_dir / f"validation_report_{timestamp}.json"

            # Save report
            with open(report_file, 'w') as f:
                json.dump(self._result.to_dict(), f, indent=2)

            self.logger.info(f"Report saved to: {report_file}")
            return str(report_file)

        except Exception as e:
            self.logger.error(f"Failed to save report: {str(e)}")
            return None

    def _log_summary(self) -> None:
        """Log pipeline execution summary."""
        self.logger.info("\n" + "=" * 80)
        self.logger.info("PIPELINE EXECUTION SUMMARY")
        self.logger.info("=" * 80)
        self.logger.info(f"Status: {self._result.status.value.upper()}")
        self.logger.info(f"Duration: {self._result.duration:.2f} seconds")
        self.logger.info(f"Total Issues Detected: {self._result.total_issues}")
        self.logger.info(
            f"Total Corrections Proposed: {self._result.total_corrections_proposed}"
        )
        self.logger.info(
            f"Total Corrections Applied: {self._result.total_corrections_applied}"
        )

        if self._result.error_message:
            self.logger.error(f"Error: {self._result.error_message}")

        if self._result.report_path:
            self.logger.info(f"Report saved to: {self._result.report_path}")

        # Log agent-specific summaries
        self.logger.info("\n" + "-" * 80)
        self.logger.info("AGENT RESULTS:")
        self.logger.info("-" * 80)

        for agent_result in self._result.agent_results:
            self.logger.info(
                f"\n{agent_result.agent_name}: {agent_result.status.value}"
            )
            if agent_result.duration:
                self.logger.info(f"  Duration: {agent_result.duration:.2f}s")
            if agent_result.metadata:
                self.logger.info("  Metadata:")
                for key, value in agent_result.metadata.items():
                    self.logger.info(f"    {key}: {value}")
            if agent_result.issues_by_severity:
                self.logger.info("  Issues by Severity:")
                for severity, count in agent_result.issues_by_severity.items():
                    if count > 0:
                        self.logger.info(f"    {severity}: {count}")

        self.logger.info("\n" + "=" * 80)
        self.logger.info("PIPELINE COMPLETE")
        self.logger.info("=" * 80)

    def get_issues_by_type(self) -> Dict[str, List[ValidationIssue]]:
        """Get all validation issues grouped by type."""
        if not self._result:
            return {}

        issues_by_type = {}
        for agent_result in self._result.agent_results:
            for issue in agent_result.issues_detected:
                issue_type = issue.issue_type.value
                if issue_type not in issues_by_type:
                    issues_by_type[issue_type] = []
                issues_by_type[issue_type].append(issue)

        return issues_by_type

    def get_issues_by_severity(self) -> Dict[str, List[ValidationIssue]]:
        """Get all validation issues grouped by severity."""
        if not self._result:
            return {}

        issues_by_severity = {}
        for agent_result in self._result.agent_results:
            for issue in agent_result.issues_detected:
                severity = issue.severity.value
                if severity not in issues_by_severity:
                    issues_by_severity[severity] = []
                issues_by_severity[severity].append(issue)

        return issues_by_severity

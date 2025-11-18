"""
Base agent class for the multi-agent data validation pipeline.

This module provides the abstract base class that all validation agents
must inherit from, ensuring a consistent interface across the pipeline.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime
from enum import Enum
import logging


class AgentStatus(Enum):
    """Status of agent execution."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class IssueType(Enum):
    """Types of issues that can be detected."""
    MISSING_DATA = "missing_data"
    INVALID_FORMAT = "invalid_format"
    INCONSISTENT_SCHEDULE = "inconsistent_schedule"
    DUPLICATE_DATA = "duplicate_data"
    REFERENCE_ERROR = "reference_error"
    BUSINESS_RULE_VIOLATION = "business_rule_violation"
    DATA_QUALITY = "data_quality"


class IssueSeverity(Enum):
    """Severity levels for detected issues."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class ValidationIssue:
    """Represents a single validation issue detected by an agent."""
    issue_type: IssueType
    severity: IssueSeverity
    message: str
    entity_type: str  # e.g., "Address", "Schedule", "PickupZone"
    entity_id: Optional[int] = None
    field_name: Optional[str] = None
    current_value: Optional[Any] = None
    expected_value: Optional[Any] = None
    correctable: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert issue to dictionary format."""
        return {
            "issue_type": self.issue_type.value,
            "severity": self.severity.value,
            "message": self.message,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "field_name": self.field_name,
            "current_value": self.current_value,
            "expected_value": self.expected_value,
            "correctable": self.correctable,
            "metadata": self.metadata
        }


@dataclass
class CorrectionAction:
    """Represents a correction action to fix a validation issue."""
    issue: ValidationIssue
    action_type: str  # e.g., "update", "delete", "create"
    entity_type: str
    entity_id: Optional[int] = None
    changes: Dict[str, Any] = field(default_factory=dict)
    executed: bool = False
    success: bool = False
    error_message: Optional[str] = None
    timestamp: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert correction action to dictionary format."""
        return {
            "action_type": self.action_type,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "changes": self.changes,
            "executed": self.executed,
            "success": self.success,
            "error_message": self.error_message,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "issue": self.issue.to_dict()
        }


@dataclass
class AgentResult:
    """Result object returned by agent execution."""
    agent_name: str
    status: AgentStatus
    issues_detected: List[ValidationIssue] = field(default_factory=list)
    corrections_proposed: List[CorrectionAction] = field(default_factory=list)
    corrections_applied: List[CorrectionAction] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    @property
    def duration(self) -> Optional[float]:
        """Calculate duration in seconds."""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None

    @property
    def issues_by_severity(self) -> Dict[str, int]:
        """Count issues by severity level."""
        counts = {severity.value: 0 for severity in IssueSeverity}
        for issue in self.issues_detected:
            counts[issue.severity.value] += 1
        return counts

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary format."""
        return {
            "agent_name": self.agent_name,
            "status": self.status.value,
            "issues_detected": [issue.to_dict() for issue in self.issues_detected],
            "corrections_proposed": [corr.to_dict() for corr in self.corrections_proposed],
            "corrections_applied": [corr.to_dict() for corr in self.corrections_applied],
            "metadata": self.metadata,
            "error_message": self.error_message,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration": self.duration,
            "issues_by_severity": self.issues_by_severity
        }


class BaseAgent(ABC):
    """
    Abstract base class for all validation agents.

    All agents in the pipeline must inherit from this class and implement
    the abstract methods. This ensures a consistent interface and makes
    it easy to add new agents to the pipeline.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the agent.

        Args:
            config: Optional configuration dictionary for the agent
        """
        self.config = config or {}
        self.logger = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")
        self._result: Optional[AgentResult] = None

    @property
    @abstractmethod
    def agent_name(self) -> str:
        """Return the unique name of this agent."""
        pass

    @property
    def result(self) -> Optional[AgentResult]:
        """Get the result of the last execution."""
        return self._result

    def run(self, context: Dict[str, Any]) -> AgentResult:
        """
        Execute the agent with the given context.

        This method wraps the _execute method with logging and error handling.

        Args:
            context: Dictionary containing execution context (data, config, etc.)

        Returns:
            AgentResult with execution details and findings
        """
        self.logger.info(f"Starting agent: {self.agent_name}")

        self._result = AgentResult(
            agent_name=self.agent_name,
            status=AgentStatus.RUNNING,
            start_time=datetime.utcnow()
        )

        try:
            self._execute(context)
            if self._result.status == AgentStatus.RUNNING:
                self._result.status = AgentStatus.SUCCESS

            self.logger.info(
                f"Agent {self.agent_name} completed: "
                f"{len(self._result.issues_detected)} issues detected, "
                f"{len(self._result.corrections_applied)} corrections applied"
            )

        except Exception as e:
            self.logger.error(f"Agent {self.agent_name} failed: {str(e)}", exc_info=True)
            self._result.status = AgentStatus.FAILED
            self._result.error_message = str(e)

        finally:
            self._result.end_time = datetime.utcnow()

        return self._result

    @abstractmethod
    def _execute(self, context: Dict[str, Any]) -> None:
        """
        Execute the agent's main logic.

        Subclasses must implement this method to perform their specific tasks.
        They should populate self._result with issues, corrections, and metadata.

        Args:
            context: Dictionary containing execution context
        """
        pass

    def _add_issue(self, issue: ValidationIssue) -> None:
        """Add an issue to the result."""
        if self._result:
            self._result.issues_detected.append(issue)
            self.logger.debug(
                f"Issue detected: {issue.issue_type.value} - {issue.message}"
            )

    def _add_correction(self, correction: CorrectionAction, applied: bool = False) -> None:
        """Add a correction action to the result."""
        if self._result:
            if applied:
                self._result.corrections_applied.append(correction)
            else:
                self._result.corrections_proposed.append(correction)
            self.logger.debug(
                f"Correction {'applied' if applied else 'proposed'}: "
                f"{correction.action_type} for {correction.entity_type}"
            )

    def _update_metadata(self, key: str, value: Any) -> None:
        """Update result metadata."""
        if self._result:
            self._result.metadata[key] = value

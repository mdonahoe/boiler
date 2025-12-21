"""
Base classes and protocols for Stage 3: Repair Execution.

Executors execute RepairPlan objects and return RepairResult objects.
"""

import typing as T
from abc import ABC, abstractmethod

from pipeline.models import RepairPlan, RepairResult


class Executor(ABC):
    """
    Base class for repair executors.

    Each executor takes a RepairPlan and executes it, ensuring that all
    changes are safe and validated.
    """

    @abstractmethod
    def execute(self, plan: RepairPlan) -> RepairResult:
        """
        Execute a repair plan and return the result.

        Args:
            plan: The repair plan to execute

        Returns:
            RepairResult indicating success/failure and files modified
        """
        pass

    @abstractmethod
    def can_handle(self, action: str) -> bool:
        """
        Check if this executor can handle a specific action.

        Args:
            action: The action type (e.g., "restore_full")

        Returns:
            True if this executor can handle this action
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name for this executor"""
        pass

    def validate_plan(self, plan: RepairPlan) -> T.Tuple[bool, T.Optional[str]]:
        """
        Validate that a plan is safe to execute.

        Args:
            plan: The plan to validate

        Returns:
            (is_valid, error_message) tuple
        """
        # Base implementation - subclasses can override
        return (True, None)

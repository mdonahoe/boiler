"""
Base classes and protocols for Stage 2: Repair Planning.

Planners convert ErrorClue objects into RepairPlan objects.
"""

import typing as T
from abc import ABC, abstractmethod

from pipeline.models import ErrorClue, RepairPlan, GitState


class Planner(ABC):
    """
    Base class for repair planners.

    Each planner takes ErrorClue objects and converts them into concrete
    RepairPlan objects that can be executed.
    """

    @abstractmethod
    def plan(self, clue: ErrorClue, git_state: GitState) -> T.List[RepairPlan]:
        """
        Convert an ErrorClue into one or more RepairPlan objects.

        Args:
            clue: The error clue to plan a fix for
            git_state: Current git repository state

        Returns:
            List of RepairPlan objects (can be empty if no plan possible)
        """
        pass

    @abstractmethod
    def can_handle(self, clue_type: str) -> bool:
        """
        Check if this planner can handle a specific clue type.

        Args:
            clue_type: The type of ErrorClue (e.g., "permission_error")

        Returns:
            True if this planner can handle this clue type
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name for this planner"""
        pass

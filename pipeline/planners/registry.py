"""
Registry for managing all repair planners.
"""

import os
import typing as T
from pipeline.planners.base import Planner
from pipeline.models import ErrorClue, RepairPlan, GitState


class PlannerRegistry:
    """
    Central registry for all repair planners.

    Manages registration and execution of planners.
    """

    def __init__(self):
        self._planners: T.List[Planner] = []

    def register(self, planner: Planner) -> None:
        """Register a new planner"""
        self._planners.append(planner)

    def plan_all(self, clues: T.List[ErrorClue], git_state: GitState) -> T.List[RepairPlan]:
        """
        Run all planners and return all RepairPlan objects.

        Each planner receives ALL clues and filters to the ones it cares about.
        This allows planners to combine context from multiple clue types.

        Args:
            clues: List of ErrorClue objects from detectors
            git_state: Current git repository state

        Returns:
            List of all RepairPlan objects, sorted by priority
        """
        all_plans: T.List[RepairPlan] = []

        # Get unique clue types to determine which planners to call
        clue_types = set(clue.clue_type for clue in clues)

        # Suppress output during tests unless BOIL_VERBOSE is set
        verbose = os.environ.get("BOIL_VERBOSE", "").lower() in ("1", "true", "yes")
        
        for planner in self._planners:
            # Check if this planner handles any of the clue types we have
            if not any(planner.can_handle(ct) for ct in clue_types):
                continue

            try:
                plans = planner.plan(clues, git_state)
                if plans:
                    if verbose:
                        print(f"[Planner:{planner.name}] Generated {len(plans)} plan(s)")
                    all_plans.extend(plans)
            except Exception as e:
                if verbose:
                    print(f"[Planner:{planner.name}] Error planning: {e}")
                    import traceback
                    traceback.print_exc()
                # Continue with other planners

        # Sort plans by priority (lower = higher priority)
        all_plans.sort(key=lambda p: p.priority)

        return all_plans

    def list_planners(self) -> T.List[str]:
        """Return list of registered planner names"""
        return [p.name for p in self._planners]


# Global registry instance
_registry = PlannerRegistry()


def register_planner(planner: Planner) -> None:
    """Register a planner with the global registry"""
    _registry.register(planner)


def get_planner_registry() -> PlannerRegistry:
    """Get the global planner registry"""
    return _registry

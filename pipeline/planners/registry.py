"""
Registry for managing all repair planners.
"""

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
        Run all applicable planners and return all RepairPlan objects.

        Args:
            clues: List of ErrorClue objects from detectors
            git_state: Current git repository state

        Returns:
            List of all RepairPlan objects, sorted by priority
        """
        all_plans: T.List[RepairPlan] = []

        for clue in clues:
            # Find planners that can handle this clue type
            for planner in self._planners:
                if not planner.can_handle(clue.clue_type):
                    continue

                try:
                    plans = planner.plan(clue, git_state)
                    if plans:
                        print(f"[Planner:{planner.name}] Generated {len(plans)} plan(s) for {clue.clue_type}")
                        all_plans.extend(plans)
                except Exception as e:
                    print(f"[Planner:{planner.name}] Error planning for {clue.clue_type}: {e}")
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

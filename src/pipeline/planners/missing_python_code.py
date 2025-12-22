"""
Planner for missing Python code (classes, functions, imports).
"""

import os
import typing as T
from src.pipeline.planners.base import Planner
from src.pipeline.models import ErrorClue, RepairPlan, GitState
from src.pipeline.utils import is_verbose


class MissingPythonCodePlanner(Planner):
    """
    Plan fixes for missing Python code (classes, functions, imports).

    Strategy:
    - Target only files that are modified or deleted (not fully restored)
    - Use src_repair to restore the missing code element
    """

    @property
    def name(self) -> str:
        return "MissingPythonCodePlanner"

    def can_handle(self, clue_type: str) -> bool:
        return clue_type == "missing_python_code"

    def plan(self, clues: T.List[ErrorClue], git_state: GitState) -> T.List[RepairPlan]:
        plans = []
        for clue in clues:
            if clue.clue_type != "missing_python_code":
                continue
            plans.extend(self._plan_for_clue(clue, git_state))
        return plans

    def _plan_for_clue(self, clue: ErrorClue, git_state: GitState) -> T.List[RepairPlan]:
        missing_element = clue.context.get("missing_element")

        if not missing_element:
            if is_verbose():
                print(f"[Planner:MissingPythonCodePlanner] Requires missing_element")
            return []

        # TODO(matt): search git for any python files that define this element.
        return []

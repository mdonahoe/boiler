"""
Planner for missing Python code (classes, functions, imports).
"""

import os
import typing as T
from pipeline.planners.base import Planner
from pipeline.models import ErrorClue, RepairPlan, GitState
from pipeline.utils import is_verbose


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
        file_path = clue.context.get("file_path")
        missing_element = clue.context.get("missing_element")

        if not file_path or not missing_element:
            if is_verbose():
                print(f"[Planner:MissingPythonCodePlanner] Missing file_path or missing_element")
            return []

        # Extract element_name and element_type from missing_element
        # missing_element is like "def foo", "class Bar", "import baz"
        parts = missing_element.split(None, 1)
        if len(parts) < 2:
            return []
        element_type = parts[0]  # "def", "class", or "import"
        # Extract just the name (handle "def foo()" -> "foo")
        element_name = parts[1].split('(')[0].strip()

        # Make path relative if it's absolute
        if os.path.isabs(file_path):
            file_path = os.path.relpath(file_path)

        # Only plan repairs for files that exist (modified) or are in the repo
        # Skip files that already fully match git
        if os.path.exists(file_path):
            # File exists - this is good, we can use src_repair to add the missing code
            if is_verbose():
                print(f"[Planner:MissingPythonCodePlanner] File {file_path} exists, planning repair")
            pass
        else:
            # File doesn't exist - skip it, let other handlers deal with full restoration
            if is_verbose():
                print(f"[Planner:MissingPythonCodePlanner] File {file_path} does not exist, skipping")
            return []

        return [
            RepairPlan(
                plan_type="restore_python_code",
                priority=0,  # High priority - missing code in test file
                target_file=file_path,
                action="restore_python_element",
                params={
                    "ref": git_state.ref,
                    "element_name": element_name,
                    "element_type": element_type,
                    "missing_element": missing_element
                },
                reason=f"Missing {element_type} '{element_name}' in {file_path}",
                clue_source=clue
            )
        ]

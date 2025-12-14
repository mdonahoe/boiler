"""
Planner for Python NameError exceptions.
"""

import os
import typing as T
from pipeline.planners.base import Planner
from pipeline.models import ErrorClue, RepairPlan, GitState
from pipeline.utils import is_verbose


class PythonNameErrorPlanner(Planner):
    """
    Plan fixes for Python NameError exceptions.

    Strategy:
    - Use src_repair to restore the missing import or code element
    - Only target existing files (not deleted files)
    """

    @property
    def name(self) -> str:
        return "PythonNameErrorPlanner"

    def can_handle(self, clue_type: str) -> bool:
        return clue_type == "python_name_error"

    def plan(self, clues: T.List[ErrorClue], git_state: GitState) -> T.List[RepairPlan]:
        plans = []
        for clue in clues:
            if clue.clue_type != "python_name_error":
                continue
            plans.extend(self._plan_for_clue(clue, git_state))
        return plans

    def _plan_for_clue(self, clue: ErrorClue, git_state: GitState) -> T.List[RepairPlan]:
        file_path = clue.context.get("file_path")
        undefined_name = clue.context.get("undefined_name")
        line_number = clue.context.get("line_number")

        if not file_path or not undefined_name:
            if is_verbose():
                print(f"[Planner:PythonNameErrorPlanner] Missing file_path or undefined_name")
            return []

        # Make path relative if it's absolute
        if os.path.isabs(file_path):
            file_path = os.path.relpath(file_path)

        # Only plan repairs for files that exist
        if os.path.exists(file_path):
            if is_verbose():
                print(f"[Planner:PythonNameErrorPlanner] File {file_path} exists, planning repair for '{undefined_name}'")
            pass
        else:
            if is_verbose():
                print(f"[Planner:PythonNameErrorPlanner] File {file_path} does not exist, skipping")
            return []

        return [
            RepairPlan(
                plan_type="restore_python_code",
                priority=0,  # High priority - NameError blocks execution
                target_file=file_path,
                action="restore_python_element",
                params={
                    "ref": git_state.ref,
                    "element_name": undefined_name,
                    "line_number": line_number,
                },
                reason=f"NameError: name '{undefined_name}' is not defined in {file_path}",
                clue_source=clue
            )
        ]

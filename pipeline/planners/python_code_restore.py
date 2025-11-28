"""
Planners for restoring missing Python code (classes, functions, imports).
"""

import os
import typing as T
from pipeline.planners.base import Planner
from pipeline.models import ErrorClue, RepairPlan, GitState


class MissingPythonCodePlanner(Planner):
    """
    Plan fixes for missing Python code (classes, functions, imports).

    Strategy:
    - Target only files that are modified or deleted (not fully restored)
    - Use py_repair to restore the missing code element
    """

    @property
    def name(self) -> str:
        return "MissingPythonCodePlanner"

    def can_handle(self, clue_type: str) -> bool:
        return clue_type == "missing_python_code"

    def plan(self, clue: ErrorClue, git_state: GitState) -> T.List[RepairPlan]:
        file_path = clue.context.get("file_path")
        element_name = clue.context.get("element_name")
        missing_element = clue.context.get("missing_element")

        if not file_path or not element_name:
            print(f"[Planner:MissingPythonCodePlanner] Missing file_path or element_name")
            return []

        # Make path relative if it's absolute
        if os.path.isabs(file_path):
            file_path = os.path.relpath(file_path)

        # Only plan repairs for files that exist (modified) or are in the repo
        # Skip files that already fully match git
        if os.path.exists(file_path):
            # File exists - this is good, we can use py_repair to add the missing code
            print(f"[Planner:MissingPythonCodePlanner] File {file_path} exists, planning repair")
            pass
        else:
            # File doesn't exist - skip it, let other handlers deal with full restoration
            print(f"[Planner:MissingPythonCodePlanner] File {file_path} does not exist, skipping")
            return []

        return [RepairPlan(
            plan_type="restore_python_code",
            priority=0,  # High priority - missing code in test file
            target_file=file_path,
            action="restore_python_element",
            params={
                "ref": git_state.ref,
                "element_name": element_name,
                "element_type": clue.context.get("element_type", "def"),
                "missing_element": missing_element
            },
            reason=f"Missing {clue.context.get('element_type', 'code')} '{element_name}' in {file_path}",
            clue_source=clue
        )]


class PythonNameErrorPlanner(Planner):
    """
    Plan fixes for Python NameError exceptions.

    Strategy:
    - Use py_repair to restore the missing import or code element
    - Only target existing files (not deleted files)
    """

    @property
    def name(self) -> str:
        return "PythonNameErrorPlanner"

    def can_handle(self, clue_type: str) -> bool:
        return clue_type == "python_name_error"

    def plan(self, clue: ErrorClue, git_state: GitState) -> T.List[RepairPlan]:
        file_path = clue.context.get("file_path")
        undefined_name = clue.context.get("undefined_name")
        line_number = clue.context.get("line_number")

        if not file_path or not undefined_name:
            print(f"[Planner:PythonNameErrorPlanner] Missing file_path or undefined_name")
            return []

        # Make path relative if it's absolute
        if os.path.isabs(file_path):
            file_path = os.path.relpath(file_path)

        # Only plan repairs for files that exist
        if os.path.exists(file_path):
            print(f"[Planner:PythonNameErrorPlanner] File {file_path} exists, planning repair for '{undefined_name}'")
            pass
        else:
            print(f"[Planner:PythonNameErrorPlanner] File {file_path} does not exist, skipping")
            return []

        return [RepairPlan(
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
        )]

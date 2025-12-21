"""
Planner for restoring header files with C syntax errors.
"""

import os
import typing as T
from pipeline.planners.base import Planner
from pipeline.models import ErrorClue, RepairPlan, GitState
from pipeline.utils import is_verbose


class CSyntaxErrorPlanner(Planner):
    """
    Plan fixes for C syntax errors in source and header files.

    Strategy:
    - Detect when C/C++ files have syntax errors (like missing code or function declarations)
    - Restore the entire file from git to fix corruption
    """

    @property
    def name(self) -> str:
        return "CSyntaxErrorPlanner"

    def can_handle(self, clue_type: str) -> bool:
        return clue_type in ["c_syntax_error_in_header", "c_syntax_error_in_source"]

    def plan(self, clues: T.List[ErrorClue], git_state: GitState) -> T.List[RepairPlan]:
        plans = []
        seen_files = set()

        for clue in clues:
            if clue.clue_type not in ["c_syntax_error_in_header", "c_syntax_error_in_source"]:
                continue

            file_path = clue.context.get("file_path")
            if not file_path:
                if is_verbose():
                    print(f"[Planner:CSyntaxErrorPlanner] Missing file_path in clue")
                continue

            # Make path relative if it's absolute
            if os.path.isabs(file_path):
                file_path = os.path.relpath(file_path)

            # Avoid duplicate plans for the same file
            if file_path in seen_files:
                if is_verbose():
                    print(f"[Planner:CSyntaxErrorPlanner] Already planning to restore {file_path}")
                continue

            seen_files.add(file_path)

            # Check if the file exists
            if not os.path.exists(file_path):
                if is_verbose():
                    print(f"[Planner:CSyntaxErrorPlanner] File {file_path} does not exist, will be restored")

            # Check if the file is corrupted (exists but has syntax errors)
            # This is indicated by the clue itself, so we can proceed to plan restoration
            line_number = clue.context.get("line_number", "?")
            unexpected_token = clue.context.get("unexpected_token", "?")

            if is_verbose():
                print(f"[Planner:CSyntaxErrorPlanner] Planning to restore {file_path} due to syntax error at line {line_number}")

            plans.append(
                RepairPlan(
                    plan_type="restore_full",
                    priority=0,  # High priority - compilation failure
                    target_file=file_path,
                    action="restore_full",
                    params={
                        "ref": git_state.ref,
                    },
                    reason=f"C syntax error in {file_path}:{line_number} (unexpected '{unexpected_token}')",
                    clue_source=clue
                )
            )

        return plans

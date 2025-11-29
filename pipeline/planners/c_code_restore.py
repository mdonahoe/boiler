"""
Planners for restoring missing C code (includes, functions).
"""

import os
import typing as T
from pipeline.planners.base import Planner
from pipeline.models import ErrorClue, RepairPlan, GitState


class MissingCIncludePlanner(Planner):
    """
    Plan fixes for missing C includes (implicit function declarations).

    Strategy:
    - Target only files that exist (not deleted files)
    - Use src_repair to restore the missing #include directive
    """

    @property
    def name(self) -> str:
        return "MissingCIncludePlanner"

    def can_handle(self, clue_type: str) -> bool:
        return clue_type == "missing_c_include"

    def plan(self, clue: ErrorClue, git_state: GitState) -> T.List[RepairPlan]:
        file_path = clue.context.get("file_path")
        suggested_include = clue.context.get("suggested_include")
        function_name = clue.context.get("function_name")

        if not file_path:
            print(f"[Planner:MissingCIncludePlanner] Missing file_path")
            return []

        # Make path relative if it's absolute
        if os.path.isabs(file_path):
            file_path = os.path.relpath(file_path)

        # Only plan repairs for files that exist
        if not os.path.exists(file_path):
            print(f"[Planner:MissingCIncludePlanner] File {file_path} does not exist, skipping")
            return []

        # If we have a suggested include, use it; otherwise, we can't fix this
        if not suggested_include:
            print(f"[Planner:MissingCIncludePlanner] No suggested include for {function_name}, skipping")
            return []

        print(f"[Planner:MissingCIncludePlanner] Planning to restore '#include <{suggested_include}>' to {file_path}")

        return [RepairPlan(
            plan_type="restore_c_code",
            priority=0,  # High priority - compilation failure
            target_file=file_path,
            action="restore_c_element",
            params={
                "ref": git_state.ref,
                "element_name": suggested_include,
                "element_type": "include",
                "function_name": function_name,
            },
            reason=f"Missing #include <{suggested_include}> for function '{function_name}' in {file_path}",
            clue_source=clue
        )]

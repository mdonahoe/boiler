"""
Planner for restoring missing C includes (implicit function declarations).
"""

import os
import typing as T
from pipeline.planners.base import Planner
from pipeline.models import ErrorClue, RepairPlan, GitState
from pipeline.utils import is_verbose


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

    def plan(self, clues: T.List[ErrorClue], git_state: GitState) -> T.List[RepairPlan]:
        plans = []
        for clue in clues:
            if clue.clue_type != "missing_c_include":
                continue
            plans.extend(self._plan_for_clue(clue, git_state))
        return plans

    def _plan_for_clue(self, clue: ErrorClue, git_state: GitState) -> T.List[RepairPlan]:
        file_path = clue.context.get("file_path")
        suggested_include = clue.context.get("suggested_include")
        function_name = clue.context.get("function_name")
        struct_name = clue.context.get("struct_name")

        if not file_path:
            if is_verbose():
                print(f"[Planner:MissingCIncludePlanner] Missing file_path")
            return []

        # Make path relative if it's absolute
        if os.path.isabs(file_path):
            file_path = os.path.relpath(file_path)

        # Only plan repairs for files that exist
        if not os.path.exists(file_path):
            if is_verbose():
                print(f"[Planner:MissingCIncludePlanner] File {file_path} does not exist, skipping")
            return []

        # Map struct names to their required headers if not suggested
        STRUCT_TO_HEADER = {
            "termios": "termios.h",
            "winsize": "sys/ioctl.h",
            "stat": "sys/stat.h",
            "tm": "time.h",
            "sigaction": "signal.h",
            "dirent": "dirent.h",
        }

        # If we have a suggested include, use it; otherwise try to map from struct name
        if not suggested_include:
            if struct_name and struct_name in STRUCT_TO_HEADER:
                suggested_include = STRUCT_TO_HEADER[struct_name]
                if is_verbose():
                    print(f"[Planner:MissingCIncludePlanner] Mapped struct '{struct_name}' to header '{suggested_include}'")
            else:
                if is_verbose():
                    print(f"[Planner:MissingCIncludePlanner] No suggested include and can't map struct '{struct_name}', skipping")
                return []

        # Check if the include is already present in the file
        try:
            with open(file_path, 'r') as f:
                content = f.read()
                # Check for both <header.h> and "header.h" styles
                if f'#include <{suggested_include}>' in content or f'#include "{suggested_include}"' in content:
                    if is_verbose():
                        print(f"[Planner:MissingCIncludePlanner] Include <{suggested_include}> already present in {file_path}, skipping")
                    return []
        except Exception as e:
            if is_verbose():
                print(f"[Planner:MissingCIncludePlanner] Error reading {file_path}: {e}")
            return []

        reason_detail = f"function '{function_name}'" if function_name else f"struct '{struct_name}'"
        if is_verbose():
            print(f"[Planner:MissingCIncludePlanner] Planning to restore '#include <{suggested_include}>' to {file_path}")

        return [
            RepairPlan(
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
                reason=f"Missing #include <{suggested_include}> for {reason_detail} in {file_path}",
                clue_source=clue
            )
        ]

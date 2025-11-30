"""
Planners for restoring missing C code (includes, functions).
"""

import os
import typing as T
from pipeline.planners.base import Planner
from pipeline.models import ErrorClue, RepairPlan, GitState


class MissingCFunctionPlanner(Planner):
    """
    Plan fixes for missing C function definitions (implicit declarations).

    Strategy:
    - Target files where function is implicitly declared
    - Use src_repair to restore the missing function definition
    """

    @property
    def name(self) -> str:
        return "MissingCFunctionPlanner"

    def can_handle(self, clue_type: str) -> bool:
        return clue_type == "missing_c_function"

    def plan(self, clues: T.List[ErrorClue], git_state: GitState) -> T.List[RepairPlan]:
        plans = []
        for clue in clues:
            if clue.clue_type != "missing_c_function":
                continue
            plans.extend(self._plan_for_clue(clue, git_state))
        return plans

    def _plan_for_clue(self, clue: ErrorClue, git_state: GitState) -> T.List[RepairPlan]:
        file_path = clue.context.get("file_path")
        symbols = clue.context.get("symbols", [])

        if not file_path or not symbols:
            print(f"[Planner:MissingCFunctionPlanner] Missing file_path or symbols")
            return []

        # Make path relative if it's absolute
        if os.path.isabs(file_path):
            file_path = os.path.relpath(file_path)

        # Only plan repairs for files that exist
        if not os.path.exists(file_path):
            print(f"[Planner:MissingCFunctionPlanner] File {file_path} does not exist, skipping")
            return []

        print(f"[Planner:MissingCFunctionPlanner] Planning to restore {len(symbols)} function(s) to {file_path}")

        # Create a plan for each symbol
        plans = []
        for symbol in symbols:
            plans.append(RepairPlan(
                plan_type="restore_c_code",
                priority=0,  # High priority - compilation error
                target_file=file_path,
                action="restore_c_element",
                params={
                    "ref": git_state.ref,
                    "element_name": symbol,
                    "element_type": "function",
                },
                reason=f"Missing function definition '{symbol}' in {file_path}",
                clue_source=clue
            ))

        return plans


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

        # Check if the include is already present in the file
        try:
            with open(file_path, 'r') as f:
                content = f.read()
                # Check for both <header.h> and "header.h" styles
                if f'#include <{suggested_include}>' in content or f'#include "{suggested_include}"' in content:
                    print(f"[Planner:MissingCIncludePlanner] Include <{suggested_include}> already present in {file_path}, skipping")
                    return []
        except Exception as e:
            print(f"[Planner:MissingCIncludePlanner] Error reading {file_path}: {e}")
            return []

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
                reason=f"Missing #include <{suggested_include}> for function '{function_name}' in {file_path}",
                clue_source=clue
            )
        ]

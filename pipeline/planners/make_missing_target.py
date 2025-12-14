"""
Planner for make missing target errors.
"""

import os
import typing as T
from pipeline.planners.base import Planner
from pipeline.models import ErrorClue, RepairPlan, GitState
from pipeline.utils import is_verbose


class MakeMissingTargetPlanner(Planner):
    """
    Plan fixes for make missing target errors.

    Strategy:
    1. Extract directory context from make_enter_directory clues
    2. For each make_missing_target clue:
       - If target is an object file (.o), try to restore the corresponding source file
       - Use directory context if available
       - Otherwise, try to restore the missing file directly
    """

    @property
    def name(self) -> str:
        return "MakeMissingTargetPlanner"

    def can_handle(self, clue_type: str) -> bool:
        return clue_type == "make_missing_target"

    def plan(self, clues: T.List[ErrorClue], git_state: GitState) -> T.List[RepairPlan]:
        # Extract directory context from make_enter_directory clues
        directory_context = None
        for clue in clues:
            if clue.clue_type == "make_enter_directory":
                directory_context = clue.context.get("directory")
                break  # Use the first (most recent) directory

        # Process all make_missing_target clues
        plans = []
        for clue in clues:
            if clue.clue_type != "make_missing_target":
                continue

            missing_file = clue.context.get("target")
            needed_by = clue.context.get("needed_by")

            if not missing_file:
                continue

            # Convert absolute directory to relative
            subdir = directory_context
            if subdir and os.path.isabs(subdir):
                cwd = os.getcwd()
                if subdir.startswith(cwd):
                    subdir = subdir[len(cwd):].lstrip('/')

            # Priority 0: If it's an object file, restore the source file instead
            if missing_file.endswith('.o'):
                base = missing_file[:-2]  # Remove .o extension
                source_extensions = ['.c', '.cc', '.cpp', '.cxx', '.C']

                for ext in source_extensions:
                    source_file = base + ext

                    # Try with subdirectory prefix if available
                    if subdir:
                        full_path = os.path.join(subdir, source_file)
                        plans.append(RepairPlan(
                            plan_type="restore_file",
                            priority=0,  # High priority - source files needed for build
                            target_file=full_path,
                            action="restore_full",
                            params={"ref": git_state.ref},
                            reason=f"Restore source file {full_path} (object file {missing_file} is needed by {needed_by})",
                            clue_source=clue
                        ))

                    # Also try without subdirectory
                    plans.append(RepairPlan(
                        plan_type="restore_file",
                        priority=0,
                        target_file=source_file,
                        action="restore_full",
                        params={"ref": git_state.ref},
                        reason=f"Restore source file {source_file} (object file {missing_file} is needed by {needed_by})",
                        clue_source=clue
                    ))

            # Priority 1: Try to restore the file directly with subdirectory
            if subdir:
                full_path = os.path.join(subdir, missing_file)
                plans.append(RepairPlan(
                    plan_type="restore_file",
                    priority=1,  # Medium priority
                    target_file=full_path,
                    action="restore_full",
                    params={"ref": git_state.ref},
                    reason=f"Restore {full_path} (needed by {needed_by})",
                    clue_source=clue
                ))

            # Priority 2: Try to restore the file directly without subdirectory
            plans.append(RepairPlan(
                plan_type="restore_file",
                priority=2,  # Lower priority - less specific
                target_file=missing_file,
                action="restore_full",
                params={"ref": git_state.ref},
                reason=f"Restore {missing_file} (needed by {needed_by})",
                clue_source=clue
            ))

        return plans

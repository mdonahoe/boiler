"""
Planner for missing directories and glob patterns.
"""

import os
import typing as T
from pipeline.planners.base import Planner
from pipeline.models import ErrorClue, RepairPlan, GitState
from pipeline.utils import is_verbose


class MissingDirectoryPlanner(Planner):
    """
    Plan fixes for missing directories and glob patterns.

    Strategy:
    - Detect when a missing "file" is actually a directory
    - Detect when a missing "file" is actually a glob pattern (e.g., src/*.c)
    - Restore all matching files from git
    """

    @property
    def name(self) -> str:
        return "MissingDirectoryPlanner"

    def can_handle(self, clue_type: str) -> bool:
        return clue_type.startswith("missing_file")

    def plan(self, clues: T.List[ErrorClue], git_state: GitState) -> T.List[RepairPlan]:
        plans = []
        for clue in clues:
            if not clue.clue_type.startswith("missing_file"):
                continue

            file_path = clue.context.get("file_path")
            if not file_path:
                continue

            # Make path relative if it's absolute
            if os.path.isabs(file_path):
                file_path = os.path.relpath(file_path)

            # Check if this is a glob pattern (contains * or ?)
            if '*' in file_path or '?' in file_path:
                # This is a glob pattern - find all matching deleted files
                import fnmatch
                matching_files = [f for f in git_state.deleted_files if fnmatch.fnmatch(f, file_path)]
                if matching_files:
                    if is_verbose():
                        print(f"[Planner] {file_path} is a glob pattern matching {len(matching_files)} deleted files")

                    for deleted_file in matching_files:
                        plans.append(RepairPlan(
                            plan_type="restore_file",
                            priority=0,  # High priority - missing files are critical
                            target_file=deleted_file,
                            action="restore_full",
                            params={"ref": git_state.ref},
                            reason=f"File {deleted_file} is missing (matches glob pattern {file_path})",
                            clue_source=clue
                        ))
                    continue

            # Check if this might be a directory by looking for files in that directory
            # in the deleted files list
            directory_files = [f for f in git_state.deleted_files if f.startswith(file_path + "/")]
            if directory_files:
                # This is a directory with deleted files in it - restore all of them
                if is_verbose():
                    print(f"[Planner] {file_path} appears to be a directory with {len(directory_files)} deleted files")

                for deleted_file in directory_files:
                    plans.append(RepairPlan(
                        plan_type="restore_file",
                        priority=0,  # High priority - missing files are critical
                        target_file=deleted_file,
                        action="restore_full",
                        params={"ref": git_state.ref},
                        reason=f"File {deleted_file} is missing (part of {file_path} directory)",
                        clue_source=clue
                    ))

        return plans

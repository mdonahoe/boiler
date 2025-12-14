"""
Planner for generic missing file errors.
"""

import os
import subprocess
import typing as T
from pipeline.planners.base import Planner
from pipeline.models import ErrorClue, RepairPlan, GitState
from pipeline.utils import is_verbose


class MissingFilePlanner(Planner):
    """
    Plan fixes for generic missing file errors.

    Strategy:
    - Always try to restore missing files from git
    - For header files in C compilation errors, search in the source directory
    """

    @property
    def name(self) -> str:
        return "MissingFilePlanner"

    def can_handle(self, clue_type: str) -> bool:
        return clue_type.startswith("missing_file")

    def _find_file_in_deleted(self, filename: str, git_state: GitState) -> T.Optional[str]:
        """Try to find a matching file in the deleted files list"""
        deleted_files = git_state.deleted_files

        # Exact match first
        if filename in deleted_files:
            return filename

        # Try with various directory prefixes
        for deleted_file in deleted_files:
            if deleted_file.endswith("/" + filename):
                return deleted_file
            if deleted_file.endswith(filename) and os.path.basename(deleted_file) == filename:
                return deleted_file

        # If source directory is provided, search there
        source_dir = self._find_source_dir()
        if source_dir:
            candidate = os.path.join(source_dir, filename)
            if candidate in deleted_files:
                return candidate

        return None

    def _find_source_dir(self) -> T.Optional[str]:
        """Try to find the source file directory from context"""
        # This will be populated from the clue context if available
        return None

    def plan(self, clues: T.List[ErrorClue], git_state: GitState) -> T.List[RepairPlan]:
        plans = []
        for clue in clues:
            if not clue.clue_type.startswith("missing_file"):
                continue
            plans.extend(self._plan_for_clue(clue, git_state))
        return plans

    def _plan_for_clue(self, clue: ErrorClue, git_state: GitState) -> T.List[RepairPlan]:
        file_path = clue.context.get("file_path")
        if not file_path:
            return []

        # Make path relative if it's absolute
        if os.path.isabs(file_path):
            file_path = os.path.relpath(file_path)

        # Skip if this is a glob pattern (let MissingDirectoryPlanner handle it)
        if '*' in file_path or '?' in file_path:
            if is_verbose():
                print(f"[Planner] Skipping {file_path} - is a glob pattern (handled by MissingDirectoryPlanner)")
            return []

        # Skip if this appears to be a directory (let MissingDirectoryPlanner handle it)
        directory_files = [f for f in git_state.deleted_files if f.startswith(file_path + "/")]
        if directory_files:
            if is_verbose():
                print(f"[Planner] Skipping {file_path} - appears to be a directory (handled by MissingDirectoryPlanner)")
            return []

        # Check if we have source directory context (from C compilation errors)
        source_dir = clue.context.get("source_dir")

        # Try to find the actual path in deleted files
        actual_path = None

        if source_dir:
            # First try: source_dir/file_path
            candidate = os.path.join(source_dir, file_path)
            if candidate in git_state.deleted_files:
                actual_path = candidate
                if is_verbose():
                    print(f"[Planner] Found {file_path} in source directory: {actual_path}")

        # Fallback: search all deleted files
        if not actual_path:
            actual_path = self._find_file_in_deleted(file_path, git_state)
            if actual_path:
                if is_verbose():
                    print(f"[Planner] Found {file_path} in deleted files: {actual_path}")
        
        # If still not found but file exists locally, check if it matches git
        if not actual_path and os.path.exists(file_path):
            # File exists - check if it matches git version
            try:
                abs_path = os.path.abspath(file_path)
                git_relative_path = os.path.relpath(abs_path, git_state.git_toplevel)

                # Compare with git version
                diff_result = subprocess.run(
                    ["git", "diff", "--quiet", git_state.ref, "--", git_relative_path],
                    cwd=git_state.git_toplevel,
                    capture_output=True
                )

                if diff_result.returncode == 0:
                    # File already matches git - no plan needed
                    if is_verbose():
                        print(f"[Planner] {file_path} already exists and matches git, skipping")
                    return []
            except Exception as e:
                # If we can't check, proceed with the plan anyway
                if is_verbose():
                    print(f"[Planner] Warning: Could not verify {file_path}: {e}")

        # Use the actual path if found, otherwise use the original path
        target_file = actual_path if actual_path else file_path

        return [RepairPlan(
            plan_type="restore_file",
            priority=0,  # High priority - missing files are critical
            target_file=target_file,
            action="restore_full",
            params={"ref": git_state.ref},
            reason=f"File {file_path} is missing",
            clue_source=clue
        )]

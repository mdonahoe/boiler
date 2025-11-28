"""
Planners for file restoration operations.
"""

import os
import subprocess
import typing as T
from pipeline.planners.base import Planner
from pipeline.models import ErrorClue, RepairPlan, GitState


class PermissionFixPlanner(Planner):
    """
    Plan fixes for permission denied errors.

    Strategy:
    - If file doesn't exist: restore from git (high priority)
    - If file exists but wrong permissions: restore from git (medium priority)
    """

    @property
    def name(self) -> str:
        return "PermissionFixPlanner"

    def can_handle(self, clue_type: str) -> bool:
        return clue_type == "permission_denied"

    def plan(self, clue: ErrorClue, git_state: GitState) -> T.List[RepairPlan]:
        file_path = clue.context.get("file_path")
        if not file_path:
            return []

        # Make path relative if it's absolute
        if os.path.isabs(file_path):
            file_path = os.path.relpath(file_path)

        plans = []

        # Check if file exists
        if not os.path.exists(file_path):
            # File is missing - restore it (high priority)
            plans.append(RepairPlan(
                plan_type="restore_file",
                priority=0,  # High priority - file missing
                target_file=file_path,
                action="restore_full",
                params={"ref": git_state.ref},
                reason=f"File {file_path} is missing (permission error implies it should exist)",
                clue_source=clue
            ))
        else:
            # File exists but has wrong permissions - restore from git
            plans.append(RepairPlan(
                plan_type="restore_permissions",
                priority=1,  # Medium priority - file exists
                target_file=file_path,
                action="restore_full",
                params={"ref": git_state.ref},
                reason=f"File {file_path} has wrong permissions, restoring from git",
                clue_source=clue
            ))

        return plans


class MissingFilePlanner(Planner):
    """
    Plan fixes for generic missing file errors.

    Strategy:
    - Always try to restore missing files from git
    """

    @property
    def name(self) -> str:
        return "MissingFilePlanner"

    def can_handle(self, clue_type: str) -> bool:
        return clue_type == "missing_file"

    def plan(self, clue: ErrorClue, git_state: GitState) -> T.List[RepairPlan]:
        file_path = clue.context.get("file_path")
        if not file_path:
            return []

        # Make path relative if it's absolute
        if os.path.isabs(file_path):
            file_path = os.path.relpath(file_path)

        # Check if file actually exists and matches git
        if os.path.exists(file_path):
            # File exists - check if it matches git version
            try:
                git_toplevel = subprocess.check_output(
                    ["git", "rev-parse", "--show-toplevel"],
                    text=True
                ).strip()
                abs_path = os.path.abspath(file_path)
                git_relative_path = os.path.relpath(abs_path, git_toplevel)

                # Compare with git version
                diff_result = subprocess.run(
                    ["git", "diff", "--quiet", git_state.ref, "--", git_relative_path],
                    cwd=git_toplevel,
                    capture_output=True
                )

                if diff_result.returncode == 0:
                    # File already matches git - no plan needed
                    print(f"[Planner] {file_path} already exists and matches git, skipping")
                    return []
            except Exception as e:
                # If we can't check, proceed with the plan anyway
                print(f"[Planner] Warning: Could not verify {file_path}: {e}")

        return [RepairPlan(
            plan_type="restore_file",
            priority=0,  # High priority - missing files are critical
            target_file=file_path,
            action="restore_full",
            params={"ref": git_state.ref},
            reason=f"File {file_path} is missing",
            clue_source=clue
        )]

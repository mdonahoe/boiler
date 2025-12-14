"""
Planner for fixing permission denied errors.
"""

import os
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
        return clue_type.endswith("permission_denied")

    def plan(self, clues: T.List[ErrorClue], git_state: GitState) -> T.List[RepairPlan]:
        plans = []
        for clue in clues:
            if not clue.clue_type.endswith("permission_denied"):
                continue

            file_path = clue.context.get("file_path")
            if not file_path:
                continue

            # Make path relative if it's absolute
            if os.path.isabs(file_path):
                file_path = os.path.relpath(file_path)

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

"""
Planner for 'No rule to make target' errors.
"""

import os
import typing as T
from pipeline.planners.base import Planner
from pipeline.models import ErrorClue, RepairPlan, GitState
from pipeline.utils import is_verbose


class MakeNoRulePlanner(Planner):
    """
    Plan fixes for 'No rule to make target' errors (often indicates missing Makefile).

    Strategy:
    - Check if Makefile, makefile, or GNUmakefile is deleted
    - Restore the deleted Makefile
    """

    @property
    def name(self) -> str:
        return "MakeNoRulePlanner"

    def can_handle(self, clue_type: str) -> bool:
        return clue_type == "make_no_rule"

    def plan(self, clues: T.List[ErrorClue], git_state: GitState) -> T.List[RepairPlan]:
        plans = []

        # Filter to make_no_rule clues
        no_rule_clues = [c for c in clues if c.clue_type == "make_no_rule"]
        if not no_rule_clues:
            return plans

        # Check for common Makefile names in deleted files
        # Prioritize root Makefile over subdirectory Makefiles
        makefile_names = ['Makefile', 'makefile', 'GNUmakefile']
        
        # First, collect all deleted Makefiles, prioritizing root ones
        root_makefiles = []
        subdir_makefiles = []
        
        for makefile_name in makefile_names:
            for deleted_file in git_state.deleted_files:
                if deleted_file == makefile_name or os.path.basename(deleted_file) == makefile_name:
                    # Check if it's a root Makefile (no directory separator or just the name)
                    if deleted_file == makefile_name or '/' not in deleted_file:
                        root_makefiles.append(deleted_file)
                    else:
                        subdir_makefiles.append(deleted_file)
        
        # Prioritize root Makefiles
        prioritized_makefiles = root_makefiles + subdir_makefiles
        
        # Only restore the first (highest priority) Makefile
        if prioritized_makefiles:
            makefile_to_restore = prioritized_makefiles[0]
            if is_verbose():
                print(f"[Planner:MakeNoRulePlanner] Found deleted {makefile_to_restore}")
            # Use the first clue as the source
            clue = no_rule_clues[0]
            plans.append(RepairPlan(
                plan_type="restore_file",
                priority=0,  # High priority - Makefile needed for build
                target_file=makefile_to_restore,
                action="restore_full",
                params={"ref": git_state.ref},
                reason=f"Restore {makefile_to_restore} (no rule to make target '{clue.context.get('target')}')",
                clue_source=clue
            ))

        return plans

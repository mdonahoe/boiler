"""
Executors for restoring missing C code elements.
"""

import os
import subprocess
import typing as T
from pipeline.executors.base import Executor
from pipeline.models import RepairPlan, RepairResult


class CCodeRestoreExecutor(Executor):
    """
    Execute restoration of missing C code (includes, functions) using src_repair.

    This executor handles the "restore_c_element" action by using src_repair
    to selectively restore only the missing code element to a file.
    """

    @property
    def name(self) -> str:
        return "CCodeRestoreExecutor"

    def can_handle(self, action: str) -> bool:
        return action == "restore_c_element"

    def validate_plan(self, plan: RepairPlan) -> T.Tuple[bool, T.Optional[str]]:
        """Validate that the file exists and can be modified"""
        file_path = plan.target_file
        element_name = plan.params.get("element_name")

        if not element_name:
            return (False, "element_name parameter is required")

        # Check if file exists
        if not os.path.exists(file_path):
            return (False, f"File {file_path} does not exist")

        return (True, None)

    def execute(self, plan: RepairPlan) -> RepairResult:
        """Execute src_repair to restore the missing code element"""
        file_path = plan.target_file
        element_name = plan.params.get("element_name")
        ref = plan.params.get("ref", "HEAD")

        try:
            # Import src_repair from git root
            import sys
            git_toplevel = self._get_git_toplevel()
            if git_toplevel not in sys.path:
                sys.path.insert(0, git_toplevel)

            from src_repair import repair, get_labels

            # Check if file exists first
            if not os.path.exists(file_path):
                return RepairResult(
                    success=False,
                    plans_attempted=[plan],
                    files_modified=[],
                    error_message=f"File {file_path} does not exist"
                )

            # Note: We don't check if the element already exists here because:
            # 1. It may exist but not be declared before its first use (forward declaration needed)
            # 2. src_repair can handle both cases (existing code and new additions)
            # 3. Checking here would prevent legitimate repairs

            # Use src_repair.repair() directly
            # This will restore the file with all existing code elements PLUS the missing element
            abs_path = os.path.abspath(file_path)
            git_toplevel = self._get_git_toplevel()
            git_relative_path = os.path.relpath(abs_path, git_toplevel)

            # Call src_repair.repair() with the missing element
            # This preserves the current file's structure and only adds the missing code
            repair(file_path, ref, missing=element_name, verbose=False)

            print(f"[Executor:CCodeRestoreExecutor] Successfully restored '{element_name}' to {file_path}")
            return RepairResult(
                success=True,
                plans_attempted=[plan],
                files_modified=[git_relative_path],
                error_message=None
            )

        except Exception as e:
            import traceback
            traceback.print_exc()
            return RepairResult(
                success=False,
                plans_attempted=[plan],
                files_modified=[],
                error_message=f"Exception during C code restore: {e}"
            )

    def _get_git_toplevel(self) -> str:
        """Get the git repository root directory"""
        return subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"],
            text=True
        ).strip()

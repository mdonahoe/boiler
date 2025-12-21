"""
Executors for restoring missing Python code elements.
"""

import os
import subprocess
import typing as T
from pipeline.executors.base import Executor
from pipeline.models import RepairPlan, RepairResult
from pipeline.utils import is_verbose


class PythonCodeRestoreExecutor(Executor):
    """
    Execute restoration of missing Python code (classes, functions, imports) using src_repair.

    This executor handles the "restore_python_element" action by using src_repair
    to selectively restore only the missing code element to a file.
    """

    @property
    def name(self) -> str:
        return "PythonCodeRestoreExecutor"

    def can_handle(self, action: str) -> bool:
        return action == "restore_python_element"

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

            from src_repair import repair

            # Check if file exists first
            if not os.path.exists(file_path):
                return RepairResult(
                    success=False,
                    plans_attempted=[plan],
                    files_modified=[],
                    error_message=f"File {file_path} does not exist"
                )

            # Get current file content to check if element already exists
            with open(file_path, 'r') as f:
                current_content = f.read()

            # Check if the element is already properly defined in the current content
            # Use src_repair's get_labels to see if it's actually there as a code element
            from src_repair import get_labels
            current_labels = get_labels(current_content)

            # Check if this element already exists as an import, class, or function
            element_patterns = [
                f"import:{element_name}",
                f"alias:{element_name}",
                f"class:{element_name}",
                f"function:{element_name}",
            ]

            if any(pattern in current_labels for pattern in element_patterns):
                return RepairResult(
                    success=False,
                    plans_attempted=[plan],
                    files_modified=[],
                    error_message=f"'{element_name}' already exists in {file_path}"
                )

            # Use src_repair.repair() directly
            # This will restore the file with all existing code elements PLUS the missing element
            abs_path = os.path.abspath(file_path)
            git_toplevel = self._get_git_toplevel()
            git_relative_path = os.path.relpath(abs_path, git_toplevel)

            # Call src_repair.repair() with the missing element
            # This preserves the current file's structure and only adds the missing code
            repair(file_path, ref, missing=element_name, verbose=False)

            if is_verbose():
                print(f"[Executor:PythonCodeRestoreExecutor] Successfully restored '{element_name}' to {file_path}")
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
                error_message=f"Exception during python code restore: {e}"
            )

    def _get_git_toplevel(self) -> str:
        """Get the git repository root directory"""
        return subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"],
            text=True
        ).strip()

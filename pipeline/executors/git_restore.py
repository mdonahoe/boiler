"""
Executors for git-based file restoration.
"""

import os
import subprocess
import typing as T
from pipeline.executors.base import Executor
from pipeline.models import RepairPlan, RepairResult


class GitRestoreExecutor(Executor):
    """
    Execute file restoration from git.

    This executor handles the "restore_full" action by checking out files from git.
    All operations are validated to ensure they're safe.
    """

    @property
    def name(self) -> str:
        return "GitRestoreExecutor"

    def can_handle(self, action: str) -> bool:
        return action == "restore_full"

    def validate_plan(self, plan: RepairPlan) -> T.Tuple[bool, T.Optional[str]]:
        """Validate that the file exists in git at the specified ref"""
        ref = plan.params.get("ref", "HEAD")
        file_path = plan.target_file

        # Check if file exists in git at ref
        try:
            git_toplevel = self._get_git_toplevel()
            cwd = os.getcwd()
            abs_path = os.path.abspath(file_path)
            git_relative_path = os.path.relpath(abs_path, git_toplevel)

            # Try to show the file from git
            result = subprocess.run(
                ["git", "show", f"{ref}:{git_relative_path}"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=git_toplevel
            )

            if result.returncode != 0:
                return (False, f"File {git_relative_path} not found in git at {ref}")

            return (True, None)
        except Exception as e:
            return (False, f"Validation error: {e}")

    def execute(self, plan: RepairPlan) -> RepairResult:
        """Execute git checkout to restore the file"""
        ref = plan.params.get("ref", "HEAD")
        file_path = plan.target_file

        try:
            git_toplevel = self._get_git_toplevel()
            cwd = os.getcwd()
            abs_path = os.path.abspath(file_path)
            git_relative_path = os.path.relpath(abs_path, git_toplevel)

            # Create parent directories if needed
            parent_dir = os.path.dirname(file_path)
            if parent_dir:
                os.makedirs(parent_dir, exist_ok=True)

            # Perform git checkout
            result = subprocess.run(
                ["git", "-C", git_toplevel, "checkout", ref, "--", git_relative_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            if result.returncode != 0:
                return RepairResult(
                    success=False,
                    plans_attempted=[plan],
                    files_modified=[],
                    error_message=f"git checkout failed: {result.stderr}"
                )

            # Verify file exists after checkout
            if not os.path.exists(file_path):
                return RepairResult(
                    success=False,
                    plans_attempted=[plan],
                    files_modified=[],
                    error_message=f"File {file_path} does not exist after git checkout"
                )

            print(f"Successfully restored {file_path} from {ref}")
            return RepairResult(
                success=True,
                plans_attempted=[plan],
                files_modified=[file_path],
                error_message=None
            )

        except Exception as e:
            return RepairResult(
                success=False,
                plans_attempted=[plan],
                files_modified=[],
                error_message=f"Exception during git restore: {e}"
            )

    def _get_git_toplevel(self) -> str:
        """Get the git repository root directory"""
        return subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"],
            text=True
        ).strip()

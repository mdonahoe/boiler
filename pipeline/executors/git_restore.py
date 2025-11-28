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

            # Check if there are actually changes to restore
            # If the file already exists and matches git, there's nothing to do
            if os.path.exists(file_path):
                # Compare with git version
                show_result = subprocess.run(
                    ["git", "diff", "--quiet", ref, "--", git_relative_path],
                    cwd=git_toplevel,
                    capture_output=True
                )
                if show_result.returncode == 0:
                    # File already matches git version - nothing to do
                    return RepairResult(
                        success=False,
                        plans_attempted=[plan],
                        files_modified=[],
                        error_message=f"File {file_path} already matches git version at {ref}"
                    )

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

            # Verify file exists after checkout IN THE EXPECTED LOCATION
            # Git checkout restores to git root, so check the actual git path
            restored_path = os.path.join(git_toplevel, git_relative_path)
            if not os.path.exists(restored_path):
                return RepairResult(
                    success=False,
                    plans_attempted=[plan],
                    files_modified=[],
                    error_message=f"File {git_relative_path} does not exist after git checkout"
                )

            # Verify that something actually changed
            # Check if the file now differs from the boiling branch
            diff_result = subprocess.run(
                ["git", "diff", "--quiet", "boiling", "--", git_relative_path],
                cwd=git_toplevel,
                capture_output=True
            )
            if diff_result.returncode == 0:
                # No difference from boiling branch - restore didn't help
                return RepairResult(
                    success=False,
                    plans_attempted=[plan],
                    files_modified=[],
                    error_message=f"Restoring {file_path} did not create any changes (already in boiling branch)"
                )

            print(f"Successfully restored {git_relative_path} from {ref}")
            return RepairResult(
                success=True,
                plans_attempted=[plan],
                files_modified=[git_relative_path],
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

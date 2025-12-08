"""
Executor for git-based stub file restoration.
"""

import os
import subprocess
import typing as T
from pipeline.executors.base import Executor
from pipeline.models import RepairPlan, RepairResult
from pipeline.utils import is_verbose


class GitRestoreStubExecutor(Executor):
    """
    Execute stub file creation from git.

    This executor handles the "restore_stub" action by creating an empty file
    with the same permissions as the file in git, without restoring the content.
    All operations are validated to ensure they're safe.
    """

    @property
    def name(self) -> str:
        return "GitRestoreStubExecutor"

    def can_handle(self, action: str) -> bool:
        return action == "restore_stub"

    def _resolve_git_path(self, file_path: str) -> str:
        """
        Resolve a file path to be relative to git root.

        The file_path may be:
        - Already relative to git root (from git diff output)
        - Relative to current working directory
        - Absolute path

        Returns: path relative to git root
        """
        git_toplevel = self._get_git_toplevel()

        # If path is absolute, make it relative to git root
        if os.path.isabs(file_path):
            return os.path.relpath(file_path, git_toplevel)

        # Check if the path exists when interpreted as git-root-relative
        git_root_path = os.path.join(git_toplevel, file_path)
        if os.path.exists(git_root_path) or file_path.count('/') > 0:
            # Likely already git-root-relative (or it's a path with slashes that should be)
            return file_path

        # Otherwise, treat as cwd-relative
        abs_path = os.path.abspath(file_path)
        return os.path.relpath(abs_path, git_toplevel)

    def _get_file_mode(self, ref: str, git_relative_path: str) -> T.Optional[int]:
        """
        Get the file mode (permissions) from git for a file at a specific ref.

        Args:
            ref: Git reference (e.g., "HEAD", "main")
            git_relative_path: Path relative to git root

        Returns:
            File mode as integer (e.g., 0o100644 for regular file, 0o100755 for executable)
            or None if the file cannot be found
        """
        try:
            git_toplevel = self._get_git_toplevel()
            # Use git ls-tree to get file mode
            # Format: <mode> <type> <hash>\t<filename>
            result = subprocess.run(
                ["git", "ls-tree", ref, "--", git_relative_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=git_toplevel
            )

            if result.returncode != 0 or not result.stdout.strip():
                return None

            # Parse the mode from the output
            # Example: "100644 blob abc123\tfile.txt"
            parts = result.stdout.strip().split()
            if len(parts) >= 1:
                mode_str = parts[0]
                # Convert octal string to integer
                return int(mode_str, 8)

            return None
        except Exception:
            return None

    def validate_plan(self, plan: RepairPlan) -> T.Tuple[bool, T.Optional[str]]:
        """Validate that the file exists in git at the specified ref"""
        ref = plan.params.get("ref", "HEAD")
        file_path = plan.target_file

        # Check if file exists in git at ref
        try:
            git_toplevel = self._get_git_toplevel()
            git_relative_path = self._resolve_git_path(file_path)

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
        """Execute stub file creation with permissions from git"""
        ref = plan.params.get("ref", "HEAD")
        file_path = plan.target_file

        try:
            git_toplevel = self._get_git_toplevel()
            git_relative_path = self._resolve_git_path(file_path)

            # Get the absolute path where the file should be created
            abs_file_path = os.path.join(git_toplevel, git_relative_path)

            # Create parent directories if needed
            parent_dir = os.path.dirname(abs_file_path)
            if parent_dir:
                os.makedirs(parent_dir, exist_ok=True)

            # Get file mode from git
            file_mode = self._get_file_mode(ref, git_relative_path)
            if file_mode is None:
                return RepairResult(
                    success=False,
                    plans_attempted=[plan],
                    files_modified=[],
                    error_message=f"Could not get file mode for {git_relative_path} from git at {ref}"
                )

            # Create empty file
            with open(abs_file_path, 'w') as f:
                pass  # Create empty file

            # Set permissions to match git
            # Extract just the permission bits (last 9 bits)
            permissions = file_mode & 0o777
            os.chmod(abs_file_path, permissions)

            # Verify file exists after creation
            if not os.path.exists(abs_file_path):
                return RepairResult(
                    success=False,
                    plans_attempted=[plan],
                    files_modified=[],
                    error_message=f"File {git_relative_path} does not exist after stub creation"
                )

            # Check if the stub actually makes a difference
            # (i.e., the file didn't already exist and was already empty)
            diff_result = subprocess.run(
                ["git", "diff", "--quiet", "boiling", "--", git_relative_path],
                cwd=git_toplevel,
                capture_output=True
            )
            if diff_result.returncode == 0:
                # No difference from boiling branch - stub didn't help
                return RepairResult(
                    success=False,
                    plans_attempted=[plan],
                    files_modified=[],
                    error_message=f"Creating stub for {file_path} did not create any changes (already in boiling branch)"
                )

            if is_verbose():
                print(f"Successfully created stub for {git_relative_path} with permissions {oct(permissions)}")

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
                error_message=f"Exception during stub creation: {e}"
            )

    def _get_git_toplevel(self) -> str:
        """Get the git repository root directory"""
        return subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"],
            text=True
        ).strip()

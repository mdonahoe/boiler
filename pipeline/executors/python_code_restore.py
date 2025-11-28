"""
Executors for restoring missing Python code elements.
"""

import os
import subprocess
import typing as T
from pipeline.executors.base import Executor
from pipeline.models import RepairPlan, RepairResult


class PythonCodeRestoreExecutor(Executor):
    """
    Execute restoration of missing Python code (classes, functions, imports) using py_repair.

    This executor handles the "restore_python_element" action by using py_repair
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
        """Execute py_repair to restore the missing code element"""
        file_path = plan.target_file
        element_name = plan.params.get("element_name")

        try:
            # Import py_repair from git root
            import sys
            git_toplevel = self._get_git_toplevel()
            if git_toplevel not in sys.path:
                sys.path.insert(0, git_toplevel)

            # Use py_repair's do_repair function
            # This is how the legacy handler does it
            from py_repair import filter_code, get_labels, LineAnnotator
            
            # Check if file exists first
            if not os.path.exists(file_path):
                return RepairResult(
                    success=False,
                    plans_attempted=[plan],
                    files_modified=[],
                    error_message=f"File {file_path} does not exist"
                )

            # Get current file content
            with open(file_path, 'r') as f:
                current_content = f.read()

            # If the element is already in the current content, we're done
            if element_name in current_content:
                return RepairResult(
                    success=False,
                    plans_attempted=[plan],
                    files_modified=[],
                    error_message=f"'{element_name}' already exists in {file_path}"
                )

            # Use py_repair to restore the missing element
            # Filter the git version to get only lines containing the element name
            abs_path = os.path.abspath(file_path)
            git_toplevel = self._get_git_toplevel()
            git_relative_path = os.path.relpath(abs_path, git_toplevel)

            # Get git version
            try:
                git_content = subprocess.check_output(
                    ["git", "show", f"HEAD:{git_relative_path}"],
                    cwd=git_toplevel,
                    text=True,
                    stderr=subprocess.PIPE
                )
            except subprocess.CalledProcessError:
                return RepairResult(
                    success=False,
                    plans_attempted=[plan],
                    files_modified=[],
                    error_message=f"Could not retrieve {file_path} from git"
                )

            # Use filter_code to extract lines related to the element
            patterns = [f".*{element_name}.*"]
            filtered_lines = list(filter_code(git_content, patterns))

            if not filtered_lines:
                return RepairResult(
                    success=False,
                    plans_attempted=[plan],
                    files_modified=[],
                    error_message=f"Could not extract '{element_name}' from git version"
                )

            # Extract just the code block we need from filtered output
            # Find where the actual class/function starts
            code_to_insert = []
            found_target = False
            
            for line in filtered_lines:
                # Look for the class/function definition
                if f"class {element_name}" in line or f"def {element_name}" in line:
                    found_target = True
                
                # Only include lines after we found the target
                if found_target:
                    code_to_insert.append(line)

            # Remove trailing blank lines and if __name__ section
            while code_to_insert and code_to_insert[-1].strip() == "":
                code_to_insert.pop()
            
            # Remove the if __name__ section if present
            final_code = []
            for line in code_to_insert:
                if 'if __name__' in line:
                    break
                final_code.append(line)
            
            code_to_insert_str = '\n'.join(final_code).strip()

            # Find insertion point in current file
            current_lines = current_content.split('\n')
            insertion_idx = len(current_lines)
            
            # Try to find a good insertion point (before if __name__ or at end)
            for i, line in enumerate(current_lines):
                if 'if __name__' in line:
                    insertion_idx = i
                    break

            # Insert blank line and then the code
            current_lines.insert(insertion_idx, '')
            current_lines.insert(insertion_idx + 1, code_to_insert_str)
            
            new_content = '\n'.join(current_lines)

            # Write back to file
            with open(file_path, 'w') as f:
                f.write(new_content)

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

"""
Executors for file editing operations (removing lines, etc.).
"""

import os
import re
import typing as T
from pipeline.executors.base import Executor
from pipeline.models import RepairPlan, RepairResult


class RemoveMatchingLinesExecutor(Executor):
    """
    Execute removal of lines matching a keyword from a file.

    This executor removes all lines containing a specific keyword,
    which is useful for cleaning up unwanted code (e.g., WASM references).
    """

    @property
    def name(self) -> str:
        return "RemoveMatchingLinesExecutor"

    def can_handle(self, action: str) -> bool:
        return action == "remove_matching_lines"

    def validate_plan(self, plan: RepairPlan) -> T.Tuple[bool, T.Optional[str]]:
        """Validate that the file exists and can be edited"""
        file_path = plan.target_file

        # Check if file exists
        if not os.path.exists(file_path):
            return (False, f"File {file_path} does not exist")

        # Check if file is readable
        if not os.access(file_path, os.R_OK):
            return (False, f"File {file_path} is not readable")

        # Check if file is writable
        if not os.access(file_path, os.W_OK):
            return (False, f"File {file_path} is not writable")

        # Check that keyword is provided
        keyword = plan.params.get("keyword")
        if not keyword:
            return (False, "No keyword specified for line removal")

        return (True, None)

    def execute(self, plan: RepairPlan) -> RepairResult:
        """Execute line removal from the file"""
        file_path = plan.target_file
        keyword = plan.params.get("keyword")
        case_insensitive = plan.params.get("case_insensitive", False)

        try:
            # Read the file
            with open(file_path, 'r') as f:
                lines = f.readlines()

            original_content = ''.join(lines)

            # Filter out lines containing the keyword
            if case_insensitive:
                pattern = re.compile(re.escape(keyword), re.IGNORECASE)
                filtered_lines = [line for line in lines if not pattern.search(line)]
            else:
                filtered_lines = [line for line in lines if keyword not in line]

            new_content = ''.join(filtered_lines)

            # Check if anything changed
            if original_content == new_content:
                return RepairResult(
                    success=False,
                    plans_attempted=[plan],
                    files_modified=[],
                    error_message=f"No lines containing '{keyword}' found in {file_path}"
                )

            # Write the filtered content back
            with open(file_path, 'w') as f:
                f.write(new_content)

            lines_removed = len(lines) - len(filtered_lines)
            print(f"Removed {lines_removed} line(s) containing '{keyword}' from {file_path}")

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
                error_message=f"Exception during line removal: {e}"
            )

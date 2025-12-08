"""
Planners for test failure errors.
"""

import os
import re
import subprocess
import typing as T
from pipeline.planners.base import Planner
from pipeline.models import ErrorClue, RepairPlan, GitState
from pipeline.utils import is_verbose


class TestFailurePlanner(Planner):
    """
    Plan fixes for test failures by reading test files to find referenced files.
    
    Strategy:
    1. Read the test file at the specified line number
    2. Look for file references in:
       - Command arguments (e.g., command=["./dim", "filename.txt"])
       - Assertion messages (e.g., assertIn("filename.txt", ...))
       - String literals that look like filenames
    3. Restore those files from git
    """

    @property
    def name(self) -> str:
        return "TestFailurePlanner"

    def can_handle(self, clue_type: str) -> bool:
        return clue_type in ("test_failure", "test_docstring_with_missing_file")

    def plan(self, clues: T.List[ErrorClue], git_state: GitState) -> T.List[RepairPlan]:
        plans = []
        seen_targets = set()  # Deduplicate plans for the same file

        for clue in clues:
            if clue.clue_type not in ("test_failure", "test_docstring_with_missing_file"):
                continue
            clue_plans = self._plan_for_clue(clue, git_state)
            for plan in clue_plans:
                if plan.target_file not in seen_targets:
                    plans.append(plan)
                    seen_targets.add(plan.target_file)

        return plans

    def _plan_for_clue(self, clue: ErrorClue, git_state: GitState) -> T.List[RepairPlan]:
        test_file = clue.context.get("test_file")
        line_number = clue.context.get("line_number")
        suspected_files = clue.context.get("suspected_files", [])



        # Convert line_number to int if it's a string
        if isinstance(line_number, str):
            try:
                line_number = int(line_number)
            except (ValueError, TypeError):
                line_number = None

        # For test_docstring_with_missing_file, we get a suspected_file directly
        if clue.clue_type == "test_docstring_with_missing_file":
            suspected_file = clue.context.get("suspected_file")
            if suspected_file:
                # Try to find the file in deleted files
                actual_path = self._find_file_in_deleted(suspected_file, git_state)
                if actual_path:
                    return [RepairPlan(
                        plan_type="restore_file",
                        priority=1,  # Medium priority - test files
                        target_file=actual_path,
                        action="restore_full",
                        params={"ref": git_state.ref},
                        reason=f"Restore {suspected_file} (referenced in test docstring)",
                        clue_source=clue
                    )]
            return []

        # For test_failure clues, we need the test file
        if not test_file:
            return []
        
        # Store original test_file for later use
        original_test_file = test_file
        
        # First, try to use the path as-is since it might be an absolute path in the current execution context
        test_file_path = original_test_file
        if os.path.isabs(test_file_path) and not os.path.exists(test_file_path):
            # If absolute path doesn't exist, try to make it relative
            try:
                test_file = os.path.relpath(test_file_path, git_state.git_toplevel)
                test_file_path = os.path.join(git_state.git_toplevel, test_file)
            except ValueError:
                # Can't relativize, try just the basename
                test_file = os.path.basename(test_file_path)
                test_file_path = os.path.join(git_state.git_toplevel, test_file)
        elif os.path.isabs(test_file_path) and os.path.exists(test_file_path):
            # Absolute path exists, keep using it
            pass
        else:
            # Relative path, resolve it relative to git toplevel
            if not os.path.isabs(test_file):
                test_file_path = os.path.join(git_state.git_toplevel, test_file)
        
        # Check if test file exists
        # TODO(matt): i dont think this matters. the test cant produce an error if it doesn't exist on disk.
        if not os.path.exists(test_file_path):
            # Try to find it in deleted files
            test_file_candidate = self._find_file_in_deleted(test_file, git_state)
            if test_file_candidate:
                test_file = test_file_candidate
            else:
                # Try just the basename
                basename = os.path.basename(test_file)
                test_file_candidate = self._find_file_in_deleted(basename, git_state)
                if test_file_candidate:
                    test_file = test_file_candidate
                else:
                    # Try common test directory locations
                    test_dirs = ["tests", "test", "t"]
                    found = False
                    for test_dir in test_dirs:
                        candidate_path = os.path.join(git_state.git_toplevel, test_dir, basename)
                        if os.path.exists(candidate_path):
                            test_file = os.path.join(test_dir, basename)
                            test_file_path = candidate_path
                            found = True
                            break

                    if not found:
                        # Try to find it in git (might not be deleted)
                        try:
                            result = subprocess.run(
                                ["git", "ls-files", "--", basename],
                                cwd=git_state.git_toplevel,
                                capture_output=True,
                                text=True
                            )
                            if result.stdout.strip():
                                test_file = result.stdout.strip().split('\n')[0]
                            else:
                                if is_verbose():
                                    print(f"[Planner:TestFailurePlanner] Test file {test_file} not found, skipping")
                                return []
                        except Exception:
                            if is_verbose():
                                print(f"[Planner:TestFailurePlanner] Test file {test_file} not found, skipping")
                            return []
        
        # Update test_file_path if we found it in git
        if test_file != original_test_file:
            if not os.path.isabs(test_file):
                test_file_path = os.path.join(git_state.git_toplevel, test_file)
            else:
                test_file_path = test_file
        
        # Read test file to find referenced files
        referenced_files = self._extract_file_references(test_file_path, line_number, suspected_files)
        
        # Create plans to restore referenced files
        plans = []
        for file_ref in referenced_files:
            # Try to find the file in deleted files
            actual_path = self._find_file_in_deleted(file_ref, git_state)
            if actual_path:
                plans.append(RepairPlan(
                    plan_type="restore_file",
                    priority=1,  # Medium priority - test files
                    target_file=actual_path,
                    action="restore_full",
                    params={"ref": git_state.ref},
                    reason=f"Restore {file_ref} referenced in test {clue.context.get('test_name')} at {test_file}:{line_number}",
                    clue_source=clue
                ))
        
        return plans

    def _extract_file_references(self, test_file: str, line_number: int, suspected_files: T.List[str]) -> T.List[str]:
        """Extract file references from test file around the failure line."""
        referenced_files = set(suspected_files)  # Start with suspected files

        try:
            with open(test_file, 'r') as f:
                lines = f.readlines()

            # For C test files, also look at the beginning of the file for comments describing test data
            full_text = ''.join(lines)

            # Look at context around the failure line (10 lines before, 20 lines after)
            start_line = max(0, line_number - 10)
            end_line = min(len(lines), line_number + 20)
            context_lines = lines[start_line:end_line]
            context_text = ''.join(context_lines)
            
            # Also expand backwards to find the test method definition (look up to 50 lines back for test method)
            test_method_start = max(0, line_number - 50)
            test_method_lines = lines[test_method_start:end_line]
            test_method_text = ''.join(test_method_lines)

            # Pattern 0: Files opened directly in Python code (e.g., open("filename.txt"))
            open_pattern = r'open\s*\(["\']([^"\']+\.(?:txt|md|c|h|cpp|hpp|py|json|yaml|yml|sh|dat))["\']'
            for match in re.finditer(open_pattern, context_text):
                referenced_files.add(match.group(1))

            # Pattern 1: Command arguments with filenames (Python tests)
            # Matches: command=["./dim", "filename.txt"] or command=["./dim", 'filename.txt']
            command_pattern = r'command\s*=\s*\[[^\]]*["\']([^"\']+\.(?:py|txt|md|c|h|cpp|hpp|json|yaml|yml|sh))["\']'
            for match in re.finditer(command_pattern, test_method_text):
                referenced_files.add(match.group(1))
            
            # Also match direct function calls with file args: ./dim, example.c
            direct_call_pattern = r'["\']([./]*[^"\'\s]+\.(?:py|txt|md|c|h|cpp|hpp|json|yaml|yml|sh|dat))["\']'
            for match in re.finditer(direct_call_pattern, test_method_text):
                filename = match.group(1).lstrip('./')
                if filename and not filename.startswith('/'):
                    referenced_files.add(filename)

            # Pattern 2: assertIn/assertEqual with filenames (Python tests)
            # Matches: assertIn("filename.txt", ...) or assertEqual(..., "filename.txt")
            assert_pattern = r'assert(?:In|Equal|NotIn|NotEqual)\s*\([^)]*["\']([^"\']+\.(?:py|txt|md|c|h|cpp|hpp|json|yaml|yml|sh|dat))["\']'
            for match in re.finditer(assert_pattern, context_text):
                referenced_files.add(match.group(1))

            # Pattern 3: C string literals with filenames
            # Matches: const char *filename = "file.txt" or const char *filename = "./file.txt"
            c_string_pattern = r'["\'](\./)?([^"\']+\.(?:txt|md|c|h|cpp|hpp|json|yaml|yml|sh|dat))["\']'
            for match in re.finditer(c_string_pattern, context_text):
                filename = match.group(2)  # Get the filename without ./ prefix if present
                # Only add if it looks like a data file (not source code being included)
                if not filename.endswith(('.c', '.h', '.cpp', '.hpp')):
                    referenced_files.add(filename)

            # Pattern 4: Files mentioned in comments (especially at the top of C test files)
            # Matches: ./tests/file.txt: or * ./tests/file.txt:
            comment_file_pattern = r'[*/]\s*(\./)?(?:tests/)?([^:\s]+\.(?:txt|md|json|yaml|yml|sh|dat)):'
            for match in re.finditer(comment_file_pattern, full_text[:500]):  # Just check first 500 chars
                filename = match.group(2)
                referenced_files.add(filename)

        except Exception as e:
            if is_verbose():
                print(f"[Planner:TestFailurePlanner] Error reading {test_file}: {e}")

        return list(referenced_files)

    def _find_file_in_deleted(self, filename: str, git_state: GitState) -> T.Optional[str]:
        """Try to find a matching file in the deleted or partial files list"""
        deleted_files = git_state.deleted_files
        partial_files = git_state.partial_files if git_state.partial_files else []
        
        # Exact match in deleted files first
        if filename in deleted_files:
            return filename
        
        # Try with various directory prefixes in deleted files
        for deleted_file in deleted_files:
            if deleted_file.endswith("/" + filename):
                return deleted_file
            if deleted_file.endswith(filename) and os.path.basename(deleted_file) == filename:
                return deleted_file
        
        # Also check partial_files (files that exist but are corrupted/truncated)
        for partial_file_info in partial_files:
            partial_file = partial_file_info.get("file", "")
            # Exact match
            if partial_file == filename:
                return filename
            # Match by basename
            if os.path.basename(partial_file) == filename:
                return partial_file
            # Match with prefix
            if partial_file.endswith("/" + filename):
                return partial_file
        
        return None

"""
Planners for test failure errors.
"""

import os
import re
import subprocess
import typing as T
from pipeline.planners.base import Planner
from pipeline.models import ErrorClue, RepairPlan, GitState


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
        return clue_type == "test_failure"

    def plan(self, clues: T.List[ErrorClue], git_state: GitState) -> T.List[RepairPlan]:
        plans = []
        seen_targets = set()  # Deduplicate plans for the same file
        
        for clue in clues:
            if clue.clue_type != "test_failure":
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
        
        if not test_file:
            return []
        
        # Make path relative if absolute
        original_test_file = test_file
        if os.path.isabs(test_file):
            test_file = os.path.relpath(test_file, git_state.git_toplevel)
        
        # Try to resolve test file path
        test_file_path = test_file
        if not os.path.isabs(test_file_path):
            test_file_path = os.path.join(git_state.git_toplevel, test_file_path)
        
        # Check if test file exists
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
                            print(f"[Planner:TestFailurePlanner] Test file {test_file} not found, skipping")
                            return []
                    except Exception:
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
            
            # Look at context around the failure line (10 lines before, 20 lines after)
            start_line = max(0, line_number - 10)
            end_line = min(len(lines), line_number + 20)
            context_lines = lines[start_line:end_line]
            context_text = ''.join(context_lines)
            
            # Pattern 1: Command arguments with filenames
            # Matches: command=["./dim", "filename.txt"] or command=["./dim", 'filename.txt']
            command_pattern = r'command\s*=\s*\[[^\]]*["\']([^"\']+\.(?:py|txt|md|c|h|cpp|hpp|json|yaml|yml|sh))["\']'
            for match in re.finditer(command_pattern, context_text):
                referenced_files.add(match.group(1))
            
            # Pattern 2: assertIn/assertEqual with filenames
            # Matches: assertIn("filename.txt", ...) or assertEqual(..., "filename.txt")
            assert_pattern = r'assert(?:In|Equal|NotIn|NotEqual)\s*\([^)]*["\']([^"\']+\.(?:py|txt|md|c|h|cpp|hpp|json|yaml|yml|sh))["\']'
            for match in re.finditer(assert_pattern, context_text):
                referenced_files.add(match.group(1))
            
        except Exception as e:
            print(f"[Planner:TestFailurePlanner] Error reading {test_file}: {e}")
        
        return list(referenced_files)

    def _find_file_in_deleted(self, filename: str, git_state: GitState) -> T.Optional[str]:
        """Try to find a matching file in the deleted files list"""
        deleted_files = git_state.deleted_files

        # Exact match first
        if filename in deleted_files:
            return filename

        # Try with various directory prefixes
        for deleted_file in deleted_files:
            if deleted_file.endswith("/" + filename):
                return deleted_file
            if deleted_file.endswith(filename) and os.path.basename(deleted_file) == filename:
                return deleted_file

        return None


class UnwantedContentPlanner(Planner):
    """
    Plan fixes for test failures caused by unwanted content in files.

    Strategy:
    1. Identify files that contain unwanted keywords (e.g., "wasm")
    2. Create a plan to remove lines containing those keywords
    """

    @property
    def name(self) -> str:
        return "UnwantedContentPlanner"

    def can_handle(self, clue_type: str) -> bool:
        return clue_type in ("git_grep_test_failure", "unwanted_content_in_files")

    def plan(self, clues: T.List[ErrorClue], git_state: GitState) -> T.List[RepairPlan]:
        plans = []
        seen_targets = set()  # Deduplicate plans for the same file

        for clue in clues:
            if clue.clue_type == "git_grep_test_failure":
                # Parse the output chunk to extract file info
                clue = self._parse_git_grep_clue(clue)

            if clue.clue_type not in ("unwanted_content_in_files", "git_grep_test_failure"):
                continue

            clue_plans = self._plan_for_clue(clue, git_state)
            for plan in clue_plans:
                target_key = (plan.target_file, plan.params.get("keyword"))
                if target_key not in seen_targets:
                    plans.append(plan)
                    seen_targets.add(target_key)

        return plans

    def _parse_git_grep_clue(self, clue: ErrorClue) -> ErrorClue:
        """Parse git grep output to extract file paths."""
        keyword = clue.context.get("keyword")
        search_path = clue.context.get("search_path")
        output_section = clue.context.get("output_section", "")

        # Pattern: file_path:line_content
        file_pattern = rf"({re.escape(search_path)}[^\s:]+):.*?{re.escape(keyword)}"
        found_files = {}
        for file_match in re.finditer(file_pattern, output_section, re.IGNORECASE):
            file_path = file_match.group(1)
            if file_path not in found_files:
                found_files[file_path] = []
            line_start = file_match.start()
            line_end = output_section.find('\n', line_start)
            if line_end == -1:
                line_end = len(output_section)
            full_line = output_section[line_start:line_end].strip()
            found_files[file_path].append(full_line)

        # Return a new clue with parsed data
        return ErrorClue(
            clue_type="unwanted_content_in_files",
            confidence=clue.confidence,
            context={
                "test_name": clue.context.get("test_name"),
                "keyword": keyword,
                "search_path": search_path,
                "found_files": found_files,
            },
            source_line=clue.source_line
        )

    def _plan_for_clue(self, clue: ErrorClue, git_state: GitState) -> T.List[RepairPlan]:
        keyword = clue.context.get("keyword")
        found_files = clue.context.get("found_files", {})
        test_name = clue.context.get("test_name", "unknown test")

        plans = []
        for file_path in found_files.keys():
            # Only create plans for header files (.h) to avoid breaking C source syntax
            # Removing arbitrary lines from .c files can create syntax errors
            if not file_path.endswith('.h'):
                print(f"[Planner:UnwantedContentPlanner] Skipping {file_path} - only header files supported")
                continue

            # Create plan to remove lines containing the keyword
            # The executor will validate that the file exists
            plans.append(RepairPlan(
                plan_type="remove_lines_matching",
                priority=1,  # Medium priority
                target_file=file_path,
                action="remove_matching_lines",
                params={
                    "keyword": keyword,
                    "case_insensitive": True,
                },
                reason=f"Remove lines containing '{keyword}' from {file_path} to fix test '{test_name}'",
                clue_source=clue
            ))

        return plans

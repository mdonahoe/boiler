"""
Planner for restoring header files with C syntax errors.
"""

import os
import re
import subprocess
import typing as T
from src.pipeline.planners.base import Planner
from src.pipeline.models import ErrorClue, RepairPlan, GitState
from src.pipeline.utils import is_verbose


class CSyntaxErrorPlanner(Planner):
    """
    Plan fixes for C syntax errors in source and header files.

    Strategy:
    - Detect when C/C++ files have syntax errors (like missing code or function declarations)
    - Check if the unexpected token is a macro/type defined in an included header
    - If that header is empty/partial, restore the header instead of the source file
    - Otherwise, restore the entire source file from git to fix corruption
    """

    @property
    def name(self) -> str:
        return "CSyntaxErrorPlanner"

    def can_handle(self, clue_type: str) -> bool:
        return clue_type in ["c_syntax_error_in_header", "c_syntax_error_in_source"]

    def plan(self, clues: T.List[ErrorClue], git_state: GitState) -> T.List[RepairPlan]:
        plans = []
        seen_files = set()

        for clue in clues:
            if clue.clue_type not in ["c_syntax_error_in_header", "c_syntax_error_in_source"]:
                continue

            file_path = clue.context.get("file_path")
            if not file_path:
                if is_verbose():
                    print(f"[Planner:CSyntaxErrorPlanner] Missing file_path in clue")
                continue

            # Make path relative if it's absolute
            if os.path.isabs(file_path):
                file_path = os.path.relpath(file_path)

            unexpected_token = clue.context.get("unexpected_token", "")
            line_number = clue.context.get("line_number", "?")

            # Check if the unexpected token looks like a macro/type name
            # (starts with uppercase or contains underscore prefix like array_)
            if unexpected_token and self._looks_like_macro_or_type(unexpected_token):
                # Try to find a partial header that defines this symbol
                partial_header = self._find_partial_header_for_symbol(
                    unexpected_token, file_path, git_state
                )
                if partial_header and partial_header not in seen_files:
                    seen_files.add(partial_header)
                    if is_verbose():
                        print(f"[Planner:CSyntaxErrorPlanner] Found partial header '{partial_header}' defining '{unexpected_token}', planning restore")
                    plans.append(
                        RepairPlan(
                            plan_type="restore_file",
                            priority=-1,  # Higher priority - fix headers first
                            target_file=partial_header,
                            action="restore_full",
                            params={"ref": git_state.ref},
                            reason=f"Header file '{partial_header}' defining '{unexpected_token}' is empty/partial",
                            clue_source=clue
                        )
                    )
                    continue  # Don't also plan to restore the source file

            # Avoid duplicate plans for the same file
            if file_path in seen_files:
                if is_verbose():
                    print(f"[Planner:CSyntaxErrorPlanner] Already planning to restore {file_path}")
                continue

            seen_files.add(file_path)

            # Check if the file exists
            if not os.path.exists(file_path):
                if is_verbose():
                    print(f"[Planner:CSyntaxErrorPlanner] File {file_path} does not exist, will be restored")

            if is_verbose():
                print(f"[Planner:CSyntaxErrorPlanner] Planning to restore {file_path} due to syntax error at line {line_number}")

            plans.append(
                RepairPlan(
                    plan_type="restore_full",
                    priority=0,  # High priority - compilation failure
                    target_file=file_path,
                    action="restore_full",
                    params={
                        "ref": git_state.ref,
                    },
                    reason=f"C syntax error in {file_path}:{line_number} (unexpected '{unexpected_token}')",
                    clue_source=clue
                )
            )

        return plans

    def _looks_like_macro_or_type(self, token: str) -> bool:
        """
        Check if a token looks like a macro or type name.

        Returns True for:
        - PascalCase names (e.g., Array, Scanner, TSNode)
        - SCREAMING_CASE names (e.g., ARRAY_SIZE)
        - Names with common prefixes (e.g., array_, ts_)
        """
        if not token:
            return False

        # Ignore common keywords
        keywords = {'void', 'int', 'char', 'float', 'double', 'long', 'short',
                    'unsigned', 'signed', 'const', 'static', 'extern', 'return',
                    'if', 'else', 'for', 'while', 'do', 'switch', 'case', 'break',
                    'continue', 'goto', 'default', 'sizeof', 'typedef', 'struct',
                    'union', 'enum'}
        if token.lower() in keywords:
            return False

        # PascalCase (starts with uppercase letter)
        if token[0].isupper():
            return True

        # SCREAMING_CASE (all uppercase with underscores)
        if token.isupper() and '_' in token:
            return True

        # Common macro/function prefixes
        if re.match(r'^(array_|ts_|tree_sitter_)', token, re.IGNORECASE):
            return True

        return False

    def _find_partial_header_for_symbol(
        self, symbol: str, source_file: str, git_state: GitState
    ) -> T.Optional[str]:
        """
        Find a header file that defines the given symbol and is in partial_files.

        Strategy:
        1. Get the list of headers included by the source file (from git)
        2. Check which of those headers are in partial_files
        3. For each partial header, check if it defines the symbol in git history
        """
        # Get included headers from the source file in git
        included_headers = self._get_included_headers(source_file)

        if is_verbose() and included_headers:
            print(f"[Planner:CSyntaxErrorPlanner] Source file includes: {included_headers}")

        # Build a map of partial files for quick lookup
        partial_map = {}
        for partial in git_state.partial_files:
            partial_file = partial.get("file", "")
            line_ratio = partial.get("line_ratio", "")
            if "/" in line_ratio:
                try:
                    current_lines = int(line_ratio.split("/")[0])
                    partial_map[partial_file] = current_lines
                except ValueError:
                    pass

        # Check each included header to see if it's partial and defines the symbol
        for header in included_headers:
            # Find matching partial file
            matching_partial = None
            for partial_file, current_lines in partial_map.items():
                # Match if paths overlap (header might be relative, partial_file absolute or vice versa)
                if (partial_file.endswith(header) or header.endswith(partial_file) or
                    partial_file == header):
                    if current_lines <= 2:  # Essentially empty
                        matching_partial = partial_file
                        break

            if matching_partial:
                # Verify this header defines the symbol in git history
                if self._header_defines_symbol(matching_partial, symbol):
                    return matching_partial

        # Also search git directly for headers that define the symbol
        defining_header = self._search_git_for_symbol(symbol)
        if defining_header:
            # Check if it's in partial_files
            for partial_file, current_lines in partial_map.items():
                if (partial_file.endswith(defining_header) or
                    defining_header.endswith(partial_file) or
                    partial_file == defining_header):
                    if current_lines <= 2:
                        return partial_file

        return None

    def _get_included_headers(self, source_file: str) -> T.List[str]:
        """Get list of headers included by a source file (from git HEAD)."""
        try:
            result = subprocess.run(
                ["git", "show", f"HEAD:{source_file}"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.returncode != 0:
                return []

            headers = []
            for line in result.stdout.split('\n'):
                # Match #include "header.h" or #include <header.h>
                match = re.match(r'#include\s+[<"]([^>"]+)[>"]', line)
                if match:
                    headers.append(match.group(1))
            return headers
        except (subprocess.TimeoutExpired, subprocess.SubprocessError):
            return []

    def _header_defines_symbol(self, header_path: str, symbol: str) -> bool:
        """Check if a header file defines a symbol (macro or type) in git history."""
        try:
            result = subprocess.run(
                ["git", "show", f"HEAD:{header_path}"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.returncode != 0:
                return False

            content = result.stdout
            # Check for #define symbol or typedef ... symbol
            if re.search(rf'#define\s+{re.escape(symbol)}\b', content):
                return True
            if re.search(rf'typedef\s+.*\b{re.escape(symbol)}\b', content):
                return True
            return False
        except (subprocess.TimeoutExpired, subprocess.SubprocessError):
            return False

    def _search_git_for_symbol(self, symbol: str) -> T.Optional[str]:
        """Search git history for a header that defines the given symbol."""
        try:
            # Search for #define symbol in header files
            result = subprocess.run(
                ["git", "grep", "-l", f"#define.*{symbol}", "HEAD", "--", "*.h"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.returncode == 0 and result.stdout.strip():
                # Get first matching header
                first_line = result.stdout.strip().split('\n')[0]
                if ':' in first_line:
                    return first_line.split(':', 1)[1]
            return None
        except (subprocess.TimeoutExpired, subprocess.SubprocessError):
            return None

"""
Planner for unknown type name errors - finds and adds missing header includes.
"""

import os
import re
import subprocess
import typing as T
from src.pipeline.planners.base import Planner
from src.pipeline.models import ErrorClue, RepairPlan, GitState
from src.pipeline.utils import is_verbose


class UnknownTypeNamePlanner(Planner):
    """
    Plan fixes for unknown type name errors by finding the defining header.

    Strategy:
    1. Use git grep to find which header file defines the type
    2. Add the appropriate #include directive to the source file
    """

    @property
    def name(self) -> str:
        return "UnknownTypeNamePlanner"

    def can_handle(self, clue_type: str) -> bool:
        return clue_type == "unknown_type_name"

    def plan(self, clues: T.List[ErrorClue], git_state: GitState) -> T.List[RepairPlan]:
        plans = []
        for clue in clues:
            if clue.clue_type != "unknown_type_name":
                continue
            plans.extend(self._plan_for_clue(clue, git_state))
        return plans

    def _plan_for_clue(self, clue: ErrorClue, git_state: GitState) -> T.List[RepairPlan]:
        file_path = clue.context.get("file_path")
        type_name = clue.context.get("type_name")

        if not file_path or not type_name:
            if is_verbose():
                print(f"[Planner:UnknownTypeNamePlanner] Missing file_path or type_name")
            return []

        # Make path relative if it's absolute
        if os.path.isabs(file_path):
            file_path = os.path.relpath(file_path)

        # Only plan repairs for files that exist
        if not os.path.exists(file_path):
            if is_verbose():
                print(f"[Planner:UnknownTypeNamePlanner] File {file_path} does not exist, skipping")
            return []

        # Find the header that defines this type
        header = self._find_defining_header(type_name)

        if not header:
            if is_verbose():
                print(f"[Planner:UnknownTypeNamePlanner] Could not find header for type '{type_name}'")
            return []

        # Check if the header file is in partial_files (empty or nearly empty)
        # If so, we should restore the header file itself, not add an include
        header_is_partial = self._is_header_partial(header, git_state)
        if header_is_partial:
            if is_verbose():
                print(f"[Planner:UnknownTypeNamePlanner] Header '{header}' is empty/partial, planning full restore")
            return [
                RepairPlan(
                    plan_type="restore_file",
                    priority=-1,  # Higher priority than include restoration - fix the source first
                    target_file=header,
                    action="restore_full",
                    params={"ref": git_state.ref},
                    reason=f"Header file '{header}' defining type '{type_name}' is empty/partial",
                    clue_source=clue
                )
            ]

        # Normalize the header path to what would appear in #include directive
        # E.g., "tree-sitter/lib/include/tree_sitter/api.h" -> "tree_sitter/api.h"
        normalized_header = self._normalize_include_path(header)

        # Check if the include is already present in the file
        try:
            with open(file_path, 'r') as f:
                content = f.read()
                # Check for both <header.h> and "header.h" styles
                if f'#include <{normalized_header}>' in content or f'#include "{normalized_header}"' in content:
                    if is_verbose():
                        print(f"[Planner:UnknownTypeNamePlanner] Include <{normalized_header}> already present in {file_path}, skipping")
                    return []
        except Exception as e:
            if is_verbose():
                print(f"[Planner:UnknownTypeNamePlanner] Error reading {file_path}: {e}")
            return []

        if is_verbose():
            print(f"[Planner:UnknownTypeNamePlanner] Planning to restore '#include <{normalized_header}>' to {file_path}")

        return [
            RepairPlan(
                plan_type="restore_c_code",
                priority=0,  # High priority - compilation failure
                target_file=file_path,
                action="restore_c_element",
                params={
                    "ref": git_state.ref,
                    "element_name": normalized_header,
                    "element_type": "include",
                },
                reason=f"Missing #include <{normalized_header}> for type '{type_name}' in {file_path}",
                clue_source=clue
            )
        ]

    def _is_header_partial(self, header: str, git_state: GitState) -> bool:
        """
        Check if a header file is in partial_files (empty or nearly empty).

        A header is considered partial if:
        1. It's in the partial_files list with very few lines (especially 0)
        2. It exists on disk but is empty or nearly empty compared to git
        """
        # Check partial_files list first
        for partial in git_state.partial_files:
            partial_file = partial.get("file", "")
            line_ratio = partial.get("line_ratio", "")

            # Match if the header path matches or ends with the partial file path
            if partial_file == header or header.endswith("/" + partial_file) or partial_file.endswith("/" + header):
                # Parse line ratio like "0/36" - if current lines is very low, it's partial
                if "/" in line_ratio:
                    try:
                        current_lines = int(line_ratio.split("/")[0])
                        # If the file has 0 or very few lines, it needs full restore
                        if current_lines <= 2:
                            return True
                    except ValueError:
                        pass

        # Also check if the header exists but is empty/nearly empty on disk
        if os.path.exists(header):
            try:
                with open(header, 'r') as f:
                    content = f.read().strip()
                    # If file is empty or just has a couple lines (e.g., just include guards)
                    if len(content.split('\n')) <= 2:
                        return True
            except Exception:
                pass

        return False

    def _find_defining_header(self, type_name: str) -> T.Optional[str]:
        """
        Use git grep to find which header file defines the given type.

        Searches for:
        1. typedef declarations: typedef ... TypeName;
        2. struct declarations: typedef struct TypeName { ... } TypeName;
        3. For types starting with common prefixes, search headers

        Returns the header path that can be used in #include, or None if not found.
        Prefers api.h or main headers over internal/grammar-specific headers.
        """
        # Strip "struct " prefix if present
        clean_type = type_name.replace("struct ", "").strip()

        # Try different search patterns in order of likelihood
        search_patterns = [
            # Pattern 1: typedef ... TypeName; (most common for opaque types)
            rf"typedef\s+.*\s+{re.escape(clean_type)}\s*;",
            # Pattern 2: typedef struct TypeName { ... } TypeName;
            rf"typedef\s+struct\s+{re.escape(clean_type)}\s*{{",
            # Pattern 3: struct TypeName { ... };
            rf"struct\s+{re.escape(clean_type)}\s*{{",
            # Pattern 4: Just the type name in a typedef
            rf"typedef.*{re.escape(clean_type)}",
        ]

        for pattern in search_patterns:
            try:
                # Search only in header files
                result = subprocess.run(
                    ["git", "grep", "-l", "-E", pattern, "HEAD", "--", "*.h"],
                    capture_output=True,
                    text=True,
                    timeout=2,
                )

                if result.returncode == 0 and result.stdout.strip():
                    # Get all header files found
                    headers = result.stdout.strip().split("\n")
                    header_paths = []
                    for header_line in headers:
                        # Git grep output format: "HEAD:path/to/file.h"
                        if ":" in header_line:
                            header_path = header_line.split(":", 1)[1]
                            header_paths.append(header_path)

                    if header_paths:
                        # Prefer api.h or public headers over internal ones
                        best_header = self._select_best_header(header_paths)
                        if best_header:
                            return best_header
            except (subprocess.TimeoutExpired, subprocess.SubprocessError):
                continue

        return None

    def _select_best_header(self, headers: T.List[str]) -> T.Optional[str]:
        """
        Select the best header from a list of candidates.

        Prefers:
        1. Headers named api.h
        2. Headers in include/ directories
        3. Shorter paths (more likely to be public APIs)
        4. First header as fallback
        """
        if not headers:
            return None

        # Prefer api.h
        api_headers = [h for h in headers if h.endswith("/api.h") or h == "api.h"]
        if api_headers:
            return api_headers[0]

        # Prefer headers in include/ directories
        include_headers = [h for h in headers if "/include/" in h]
        if include_headers:
            return include_headers[0]

        # Prefer shorter paths (more likely to be public APIs)
        headers_sorted = sorted(headers, key=lambda h: len(h))
        return headers_sorted[0]

    def _normalize_include_path(self, header_path: str) -> str:
        """
        Normalize a header path to what would appear in an #include directive.

        Examples:
        - "tree-sitter/lib/include/tree_sitter/api.h" -> "tree_sitter/api.h"
        - "include/foo/bar.h" -> "foo/bar.h"
        - "foo.h" -> "foo.h"

        Strategy: If the path contains "/include/", extract everything after it.
        Otherwise, return the full path.
        """
        if "/include/" in header_path:
            # Extract the part after the last "/include/"
            parts = header_path.split("/include/")
            return parts[-1]

        return header_path

"""
Planners for file restoration operations.
"""

import os
import re
import subprocess
import typing as T
from pipeline.planners.base import Planner
from pipeline.models import ErrorClue, RepairPlan, GitState


class PermissionFixPlanner(Planner):
    """
    Plan fixes for permission denied errors.

    Strategy:
    - If file doesn't exist: restore from git (high priority)
    - If file exists but wrong permissions: restore from git (medium priority)
    """

    @property
    def name(self) -> str:
        return "PermissionFixPlanner"

    def can_handle(self, clue_type: str) -> bool:
        return clue_type == "permission_denied"

    def plan(self, clue: ErrorClue, git_state: GitState) -> T.List[RepairPlan]:
        file_path = clue.context.get("file_path")
        if not file_path:
            return []

        # Make path relative if it's absolute
        if os.path.isabs(file_path):
            file_path = os.path.relpath(file_path)

        plans = []

        # Check if file exists
        if not os.path.exists(file_path):
            # File is missing - restore it (high priority)
            plans.append(RepairPlan(
                plan_type="restore_file",
                priority=0,  # High priority - file missing
                target_file=file_path,
                action="restore_full",
                params={"ref": git_state.ref},
                reason=f"File {file_path} is missing (permission error implies it should exist)",
                clue_source=clue
            ))
        else:
            # File exists but has wrong permissions - restore from git
            plans.append(RepairPlan(
                plan_type="restore_permissions",
                priority=1,  # Medium priority - file exists
                target_file=file_path,
                action="restore_full",
                params={"ref": git_state.ref},
                reason=f"File {file_path} has wrong permissions, restoring from git",
                clue_source=clue
            ))

        return plans


class MissingFilePlanner(Planner):
    """
    Plan fixes for generic missing file errors.

    Strategy:
    - Always try to restore missing files from git
    - For header files in C compilation errors, search in the source directory
    """

    @property
    def name(self) -> str:
        return "MissingFilePlanner"

    def can_handle(self, clue_type: str) -> bool:
        return clue_type == "missing_file"

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
        
        # If source directory is provided, search there
        source_dir = self._find_source_dir()
        if source_dir:
            candidate = os.path.join(source_dir, filename)
            if candidate in deleted_files:
                return candidate
        
        return None

    def _find_source_dir(self) -> T.Optional[str]:
        """Try to find the source file directory from context"""
        # This will be populated from the clue context if available
        return None

    def plan(self, clue: ErrorClue, git_state: GitState) -> T.List[RepairPlan]:
        file_path = clue.context.get("file_path")
        if not file_path:
            return []

        # Make path relative if it's absolute
        if os.path.isabs(file_path):
            file_path = os.path.relpath(file_path)

        # Check if we have source directory context (from C compilation errors)
        source_dir = clue.context.get("source_dir")
        
        # Try to find the actual path in deleted files
        actual_path = None
        
        if source_dir:
            # First try: source_dir/file_path
            candidate = os.path.join(source_dir, file_path)
            if candidate in git_state.deleted_files:
                actual_path = candidate
                print(f"[Planner] Found {file_path} in source directory: {actual_path}")
        
        # Fallback: search all deleted files
        if not actual_path:
            actual_path = self._find_file_in_deleted(file_path, git_state)
            if actual_path:
                print(f"[Planner] Found {file_path} in deleted files: {actual_path}")
        
        # If still not found but file exists locally, check if it matches git
        if not actual_path and os.path.exists(file_path):
            # File exists - check if it matches git version
            try:
                abs_path = os.path.abspath(file_path)
                git_relative_path = os.path.relpath(abs_path, git_state.git_toplevel)

                # Compare with git version
                diff_result = subprocess.run(
                    ["git", "diff", "--quiet", git_state.ref, "--", git_relative_path],
                    cwd=git_state.git_toplevel,
                    capture_output=True
                )

                if diff_result.returncode == 0:
                    # File already matches git - no plan needed
                    print(f"[Planner] {file_path} already exists and matches git, skipping")
                    return []
            except Exception as e:
                # If we can't check, proceed with the plan anyway
                print(f"[Planner] Warning: Could not verify {file_path}: {e}")

        # Use the actual path if found, otherwise use the original path
        target_file = actual_path if actual_path else file_path

        return [RepairPlan(
            plan_type="restore_file",
            priority=0,  # High priority - missing files are critical
            target_file=target_file,
            action="restore_full",
            params={"ref": git_state.ref},
            reason=f"File {file_path} is missing",
            clue_source=clue
        )]


class LinkerUndefinedSymbolsPlanner(Planner):
    """
    Plan fixes for C/C++ linker errors due to undefined symbols.

    Strategy:
    - If lib.c is deleted, restore it (it's the main compilation unit that includes others)
    - Otherwise, find C/C++ source files that define the undefined symbols
    - Restore the file(s) that contain these symbols
    """

    @property
    def name(self) -> str:
        return "LinkerUndefinedSymbolsPlanner"

    def can_handle(self, clue_type: str) -> bool:
        return clue_type == "linker_undefined_symbols"

    def plan(self, clue: ErrorClue, git_state: GitState) -> T.List[RepairPlan]:
        symbols = clue.context.get("symbols", [])
        if not symbols:
            return []

        deleted_files = git_state.deleted_files
        deleted_c_files = [f for f in deleted_files if f.endswith(('.c', '.cpp', '.cc', '.cxx', '.C'))]

        if not deleted_c_files:
            # No deleted C files - linker error might be from other causes
            return []

        # Check if lib.c is deleted - it's a special case
        lib_c_candidates = [f for f in deleted_c_files if 'lib.c' in f or f.endswith('/lib.c')]
        if lib_c_candidates:
            print(f"[Planner] Found deleted lib.c: {lib_c_candidates[0]}")
            return [RepairPlan(
                plan_type="restore_file",
                priority=0,  # Highest priority
                target_file=lib_c_candidates[0],
                action="restore_full",
                params={"ref": git_state.ref},
                reason=f"Restore {lib_c_candidates[0]} (main compilation unit)",
                clue_source=clue
            )]

        print(f"[Planner] Found {len(symbols)} undefined symbols, checking {len(deleted_c_files)} deleted C files")

        # For each deleted C file, check how many symbols it defines
        file_scores = {}
        for c_file in deleted_c_files:
            try:
                # Use git show to get the file contents
                result = subprocess.run(
                    ["git", "show", f"{git_state.ref}:{c_file}"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    cwd=git_state.git_toplevel
                )

                if result.returncode != 0:
                    continue

                file_contents = result.stdout

                # Count how many symbols are likely defined in this file
                score = 0
                matched_symbols = []
                for symbol in symbols:
                    # Look for the symbol in the file (function definition or declaration)
                    # Pattern: symbol(...) or symbol (...)
                    if re.search(rf'\b{re.escape(symbol)}\s*\(', file_contents):
                        score += 1
                        matched_symbols.append(symbol)

                if score > 0:
                    file_scores[c_file] = (score, matched_symbols)
                    print(f"[Planner]   {c_file}: {score} symbols matched")

            except Exception as e:
                print(f"[Planner] Error checking {c_file}: {e}")
                continue

        # Create plans for files with highest scores first
        plans = []
        for c_file, (score, matched_symbols) in sorted(file_scores.items(), key=lambda x: x[1][0], reverse=True):
            print(f"[Planner] Creating plan to restore {c_file} ({score} symbols)")
            plans.append(RepairPlan(
                plan_type="restore_file",
                priority=0 - (score / 100),  # Higher scores get higher priority
                target_file=c_file,
                action="restore_full",
                params={"ref": git_state.ref},
                reason=f"File {c_file} contains {score} undefined symbols: {', '.join(matched_symbols[:3])}...",
                clue_source=clue
            ))

        return plans

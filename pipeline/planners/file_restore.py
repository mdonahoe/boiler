"""
Planners for file restoration operations.
"""

import os
import re
import subprocess
import typing as T
from pipeline.planners.base import Planner
from pipeline.models import ErrorClue, RepairPlan, GitState
from pipeline.utils import is_verbose


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
        return clue_type.endswith("permission_denied")

    def plan(self, clues: T.List[ErrorClue], git_state: GitState) -> T.List[RepairPlan]:
        plans = []
        for clue in clues:
            if not clue.clue_type.endswith("permission_denied"):
                continue

            file_path = clue.context.get("file_path")
            if not file_path:
                continue

            # Make path relative if it's absolute
            if os.path.isabs(file_path):
                file_path = os.path.relpath(file_path)

            # Check if file exists
            if not os.path.exists(file_path):
                # File is missing - restore it (high priority)
                # Header files should be restored in full, source files as stubs
                is_header_file = file_path.endswith('.h') or file_path.endswith('.hpp')
                action = "restore_full" if is_header_file else "restore_stub"
                plans.append(RepairPlan(
                    plan_type="restore_file",
                    priority=0,  # High priority - file missing
                    target_file=file_path,
                    action=action,
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
                    action="restore_stub",
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
        return clue_type.startswith("missing_file")

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

    def plan(self, clues: T.List[ErrorClue], git_state: GitState) -> T.List[RepairPlan]:
        plans = []
        for clue in clues:
            if not clue.clue_type.startswith("missing_file"):
                continue
            plans.extend(self._plan_for_clue(clue, git_state))
        return plans

    def _plan_for_clue(self, clue: ErrorClue, git_state: GitState) -> T.List[RepairPlan]:
        file_path = clue.context.get("file_path")
        if not file_path:
            return []

        # Make path relative if it's absolute
        if os.path.isabs(file_path):
            file_path = os.path.relpath(file_path)

        # Skip if this is a glob pattern (let MissingDirectoryPlanner handle it)
        if '*' in file_path or '?' in file_path:
            if is_verbose():
                print(f"[Planner] Skipping {file_path} - is a glob pattern (handled by MissingDirectoryPlanner)")
            return []

        # Skip if this appears to be a directory (let MissingDirectoryPlanner handle it)
        directory_files = [f for f in git_state.deleted_files if f.startswith(file_path + "/")]
        if directory_files:
            if is_verbose():
                print(f"[Planner] Skipping {file_path} - appears to be a directory (handled by MissingDirectoryPlanner)")
            return []

        # Check if we have source directory context (from C compilation errors)
        source_dir = clue.context.get("source_dir")

        # Try to find the actual path in deleted files
        actual_path = None

        if source_dir:
            # First try: source_dir/file_path
            candidate = os.path.join(source_dir, file_path)
            if candidate in git_state.deleted_files:
                actual_path = candidate
                if is_verbose():
                    print(f"[Planner] Found {file_path} in source directory: {actual_path}")

        # Fallback: search all deleted files
        if not actual_path:
            actual_path = self._find_file_in_deleted(file_path, git_state)
            if actual_path:
                if is_verbose():
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
                    if is_verbose():
                        print(f"[Planner] {file_path} already exists and matches git, skipping")
                    return []
            except Exception as e:
                # If we can't check, proceed with the plan anyway
                if is_verbose():
                    print(f"[Planner] Warning: Could not verify {file_path}: {e}")

        # Use the actual path if found, otherwise use the original path
        target_file = actual_path if actual_path else file_path

        # Determine if this is a header file - header files should be restored in full
        # since they need complete type definitions for compilation
        is_header_file = target_file.endswith('.h') or target_file.endswith('.hpp')
        action = "restore_full" if is_header_file else "restore_stub"

        return [RepairPlan(
            plan_type="restore_file",
            priority=0,  # High priority - missing files are critical
            target_file=target_file,
            action=action,
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

    def plan(self, clues: T.List[ErrorClue], git_state: GitState) -> T.List[RepairPlan]:
        # Collect all symbols from all clues (detectors now emit one clue per symbol)
        symbols = []
        linker_clue = None
        for clue in clues:
            if clue.clue_type != "linker_undefined_symbols":
                continue
            linker_clue = clue
            # Handle both old format (symbols list) and new format (single symbol)
            if "symbols" in clue.context:
                symbols.extend(clue.context["symbols"])
            elif "symbol" in clue.context:
                symbols.append(clue.context["symbol"])

        if not symbols or not linker_clue:
            return []

        return self._plan_for_clue(symbols, linker_clue, git_state)

    def _plan_for_clue(self, symbols: T.List[str], clue: ErrorClue, git_state: GitState) -> T.List[RepairPlan]:
        if not symbols:
            return []

        deleted_files = git_state.deleted_files
        deleted_c_files = [f for f in deleted_files if f.endswith(('.c', '.cpp', '.cc', '.cxx', '.C'))]

        # Check if lib.c is deleted - it's a special case
        lib_c_candidates = [f for f in deleted_c_files if 'lib.c' in f or f.endswith('/lib.c')]
        if lib_c_candidates:
            if is_verbose():
                print(f"[Planner] Found deleted lib.c: {lib_c_candidates[0]}")
            return [RepairPlan(
                plan_type="restore_file",
                priority=0,  # Highest priority
                target_file=lib_c_candidates[0],
                action="restore_stub",
                params={"ref": git_state.ref},
                reason=f"Restore {lib_c_candidates[0]} (main compilation unit)",
                clue_source=clue
            )]

        if is_verbose():
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
                    # Look for the symbol in the file (function definition, declaration, or variable)
                    # Pattern 1: symbol(...) - function call/definition
                    # Pattern 2: \bsymbol\b - variable/symbol as a word boundary
                    if (re.search(rf'\b{re.escape(symbol)}\s*\(', file_contents) or
                        re.search(rf'\b{re.escape(symbol)}\b', file_contents)):
                        score += 1
                        matched_symbols.append(symbol)

                if score > 0:
                    file_scores[c_file] = (score, matched_symbols)
                    if is_verbose():
                        print(f"[Planner]   {c_file}: {score} symbols matched")

            except Exception as e:
                if is_verbose():
                    print(f"[Planner] Error checking {c_file}: {e}")
                continue

        # Create plans for files with highest scores first
        plans = []
        for c_file, (score, matched_symbols) in sorted(file_scores.items(), key=lambda x: x[1][0], reverse=True):
            # Check if the file exists or is deleted
            file_exists = os.path.exists(c_file)

            if file_exists:
                # File exists - restore individual functions
                if is_verbose():
                    print(f"[Planner] Creating plan to restore functions to existing file {c_file} ({score} symbols)")
                for symbol in matched_symbols:
                    plans.append(RepairPlan(
                        plan_type="restore_c_code",
                        priority=0 - (score / 100),  # Higher scores get higher priority
                        target_file=c_file,
                        action="restore_c_element",
                        params={
                            "ref": git_state.ref,
                            "element_name": symbol,
                            "element_type": "function",
                        },
                        reason=f"Restore function '{symbol}' to {c_file}",
                        clue_source=clue
                    ))
            else:
                # File is completely deleted - create stub first
                if is_verbose():
                    print(f"[Planner] File {c_file} is deleted, creating stub first")
                # Create stub
                plans.append(RepairPlan(
                    plan_type="restore_file",
                    priority=0 - (score / 100) - 0.01,  # Slightly higher priority to run first
                    target_file=c_file,
                    action="restore_stub",
                    params={"ref": git_state.ref},
                    reason=f"Create stub for {c_file} before restoring functions",
                    clue_source=clue
                ))
                # Then restore functions
                for symbol in matched_symbols:
                    plans.append(RepairPlan(
                        plan_type="restore_c_code",
                        priority=0 - (score / 100),
                        target_file=c_file,
                        action="restore_c_element",
                        params={
                            "ref": git_state.ref,
                            "element_name": symbol,
                            "element_type": "function",
                        },
                        reason=f"Restore function '{symbol}' to {c_file}",
                        clue_source=clue
                    ))

        # If no deleted files matched, check existing C files and use src_repair
        if not plans:
            if is_verbose():
                print(f"[Planner] No deleted C files matched, checking existing C files")
            # Look for existing C files that might need functions restored
            import glob
            existing_c_files = glob.glob("*.c") + glob.glob("**/*.c", recursive=True)
            
            # For linker errors, prioritize files that are likely compilation targets
            # This makes the tool generic - it works for any repo
            priority_files = []
            other_files = []
            
            # Get modified files from git to understand what's being actively worked on
            modified_set = set()
            try:
                result = subprocess.run(
                    ["git", "diff", "--name-only"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    cwd=git_state.git_toplevel
                )
                modified_set = set(line.strip() for line in result.stdout.splitlines())
            except:
                pass
            
            deleted_set = set(git_state.deleted_files)
            
            for f in existing_c_files:
                # Normalize path for comparison
                abs_f = os.path.abspath(f)
                git_relative = os.path.relpath(abs_f, git_state.git_toplevel)
                
                # Prioritize based on:
                # 1. Files that are modified in git (actively being worked on)
                # 2. Files in the deleted set (previously had content)
                # 3. Files in the root directory (likely main compilation target)
                score = 0
                if git_relative in modified_set:
                    score += 10  # Heavily prioritize modified files
                if git_relative in deleted_set:
                    score += 5
                if '/' not in f:
                    score += 1  # Slight priority for root directory files
                
                if score > 0:
                    priority_files.append((score, f))
                else:
                    other_files.append(f)
            
            # Sort priority files by score (highest first) and extract just the filenames
            priority_files.sort(key=lambda x: x[0], reverse=True)
            existing_c_files = [f for _, f in priority_files] + other_files

            for c_file in existing_c_files:
                if not os.path.exists(c_file):
                    continue

                try:
                    # Check if this file exists in git
                    result = subprocess.run(
                        ["git", "show", f"{git_state.ref}:{c_file}"],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        cwd=git_state.git_toplevel
                    )

                    if result.returncode != 0:
                        continue

                    git_contents = result.stdout

                    # Check if any undefined symbols are defined in the git version
                    for symbol in symbols:

                        # Look for function definitions (not just declarations)
                        # Pattern: return_type symbol(...) { or symbol(...) {
                        # Also match: type symbol(...) or symbol(...) with looser matching
                        patterns = [
                            rf'\b{re.escape(symbol)}\s*\([^)]*\)\s*\{{',  # Function definition with {
                            rf'^\s*\w+\s+\*?{re.escape(symbol)}\s*\(',  # With return type
                            rf'^\s*{re.escape(symbol)}\s*\(',  # Function at line start
                        ]

                        found = False
                        for pattern in patterns:
                            if re.search(pattern, git_contents, re.MULTILINE):
                                found = True
                                break

                        if found:
                            # Calculate priority based on how well the filename matches the symbol
                            # If we're looking for "main" and the file is "main.c" or "src/main.c", prioritize it
                            priority = 0
                            basename = os.path.basename(c_file)
                            basename_no_ext = os.path.splitext(basename)[0]

                            # Special priority boost if filename matches symbol (e.g., main.c for main function)
                            if basename_no_ext == symbol:
                                priority = -100  # Highest priority (most negative = highest)
                                if is_verbose():
                                    print(f"[Planner] Found function definition for '{symbol}' in {c_file} (git version) - HIGH PRIORITY (filename matches)")
                            # De-prioritize test files
                            elif 'test' in c_file.lower():
                                priority = 100  # Lower priority (more positive = lower)
                                if is_verbose():
                                    print(f"[Planner] Found function definition for '{symbol}' in {c_file} (git version) - low priority (test file)")
                            else:
                                if is_verbose():
                                    print(f"[Planner] Found function definition for '{symbol}' in {c_file} (git version)")

                            # Create a plan to restore this specific function
                            plans.append(RepairPlan(
                                plan_type="restore_c_code",
                                priority=priority,
                                target_file=c_file,
                                action="restore_c_element",
                                params={
                                    "ref": git_state.ref,
                                    "element_name": symbol,
                                    "element_type": "function",
                                },
                                reason=f"Restore function '{symbol}' to {c_file}",
                                clue_source=clue
                            ))
                            # Don't mark as planned - allow multiple plans for the same symbol
                            # to different files, so we can restore main to all files that need it

                except Exception as e:
                    if is_verbose():
                        print(f"[Planner] Error checking {c_file}: {e}")
                    continue

        return plans


class MissingDirectoryPlanner(Planner):
    """
    Plan fixes for missing directories and glob patterns.

    Strategy:
    - Detect when a missing "file" is actually a directory
    - Detect when a missing "file" is actually a glob pattern (e.g., src/*.c)
    - Restore all matching files from git
    """

    @property
    def name(self) -> str:
        return "MissingDirectoryPlanner"

    def can_handle(self, clue_type: str) -> bool:
        return clue_type.startswith("missing_file")

    def plan(self, clues: T.List[ErrorClue], git_state: GitState) -> T.List[RepairPlan]:
        plans = []
        for clue in clues:
            if not clue.clue_type.startswith("missing_file"):
                continue

            file_path = clue.context.get("file_path")
            if not file_path:
                continue

            # Make path relative if it's absolute
            if os.path.isabs(file_path):
                file_path = os.path.relpath(file_path)

            # Check if this is a glob pattern (contains * or ?)
            if '*' in file_path or '?' in file_path:
                # This is a glob pattern - find all matching deleted files
                import fnmatch
                matching_files = [f for f in git_state.deleted_files if fnmatch.fnmatch(f, file_path)]
                if matching_files:
                    if is_verbose():
                        print(f"[Planner] {file_path} is a glob pattern matching {len(matching_files)} deleted files")

                    for deleted_file in matching_files:
                        plans.append(RepairPlan(
                            plan_type="restore_file",
                            priority=0,  # High priority - missing files are critical
                            target_file=deleted_file,
                            action="restore_stub",
                            params={"ref": git_state.ref},
                            reason=f"File {deleted_file} is missing (matches glob pattern {file_path})",
                            clue_source=clue
                        ))
                    continue

            # Check if this might be a directory by looking for files in that directory
            # in the deleted files list
            directory_files = [f for f in git_state.deleted_files if f.startswith(file_path + "/")]
            if directory_files:
                # This is a directory with deleted files in it - restore all of them
                if is_verbose():
                    print(f"[Planner] {file_path} appears to be a directory with {len(directory_files)} deleted files")

                for deleted_file in directory_files:
                    plans.append(RepairPlan(
                        plan_type="restore_file",
                        priority=0,  # High priority - missing files are critical
                        target_file=deleted_file,
                        action="restore_stub",
                        params={"ref": git_state.ref},
                        reason=f"File {deleted_file} is missing (part of {file_path} directory)",
                        clue_source=clue
                    ))

        return plans

"""
Make Directory Resolver Planner Plugin

This plugin handles missing files where the path is relative to a make
subdirectory. It uses the make_enter_directory clue to determine the
current working directory and resolves relative paths accordingly.

For example:
    Error from make in /project/builtins: "./psize.sh: No such file"
    Actual file: "builtins/psize.sh"

Handles clue types:
    - missing_file: When the path is relative (starts with ./)
    - shell_cannot_open: When shell can't open a relative file
"""

def name():
    """Return the planner name for logging."""
    return "MakeDirectoryResolverPlanner"

def can_handle(clue_type):
    """Return True if this planner handles the given clue type."""
    return clue_type in ["missing_file", "shell_cannot_open", "make_enter_directory"]

def plan(clues, git_state):
    """Generate repair plans from clues."""
    plans = []

    # Find the current make directory from make_enter_directory clues
    make_dir = ""
    git_toplevel = git_state.get("git_toplevel", "")

    for clue in clues:
        if clue["clue_type"] == "make_enter_directory":
            make_dir = clue["context"].get("directory", "")
            log("MakeDirectoryResolver: Found make directory: " + make_dir)
            break

    if not make_dir:
        log("MakeDirectoryResolver: No make_enter_directory clue found")
        return plans

    # Convert absolute make_dir to relative path from git toplevel
    relative_make_dir = ""
    if git_toplevel and make_dir.startswith(git_toplevel):
        relative_make_dir = make_dir[len(git_toplevel):]
        if relative_make_dir.startswith("/"):
            relative_make_dir = relative_make_dir[1:]

    log("MakeDirectoryResolver: Relative make dir: " + relative_make_dir)

    # Process missing file clues
    seen_files = {}
    for clue in clues:
        if clue["clue_type"] not in ["missing_file", "shell_cannot_open"]:
            continue

        missing_path = clue["context"].get("file_path", "")
        if not missing_path:
            continue

        # Handle relative paths (./foo or just foo)
        clean_path = missing_path
        if clean_path.startswith("./"):
            clean_path = clean_path[2:]  # Remove ./

        # Skip absolute paths
        if clean_path.startswith("/"):
            continue

        # Construct full path relative to git toplevel
        if relative_make_dir:
            full_path = relative_make_dir + "/" + clean_path
        else:
            full_path = clean_path

        if full_path in seen_files:
            continue
        seen_files[full_path] = True

        log("MakeDirectoryResolver: Resolved path: " + missing_path + " -> " + full_path)

        # Check if this file exists in deleted files
        for deleted_file in git_state["deleted_files"]:
            # Match exactly or with git toplevel prefix
            if deleted_file == full_path or deleted_file.endswith("/" + full_path):
                log("MakeDirectoryResolver: Found deleted file: " + deleted_file)
                plans.append({
                    "plan_type": "restore_file",
                    "priority": -1,  # Higher priority than built-in
                    "target_file": deleted_file,
                    "action": "restore_full",
                    "params": {"ref": git_state["ref"]},
                    "reason": "Restore " + deleted_file + " (resolved from " + missing_path + " in " + relative_make_dir + ")",
                })
                break

    return plans

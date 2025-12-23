"""
Missing Header Resolver Planner Plugin

This plugin handles cases where a header file is missing and the error
message shows an include path that differs from the actual file path.

For example:
    Error: "fatal error: tree_sitter/api.h: No such file or directory"
    Actual file: "lib/include/tree_sitter/api.h"

The plugin searches deleted files to find one that ends with the missing
include path, allowing it to restore the correct file.

Usage:
    Copy this file to .boil/plugins/planners/ in your repository.

Handles clue types:
    - missing_file: From CCompilationErrorDetector when #include fails
"""

def name():
    """Return the planner name for logging."""
    return "MissingHeaderResolverPlanner"

def can_handle(clue_type):
    """Return True if this planner handles the given clue type."""
    return clue_type == "missing_file"

def plan(clues, git_state):
    """Generate repair plans from clues.

    Args:
        clues: List of dicts with keys: clue_type, confidence, context, source_line
        git_state: Dict with keys: ref, deleted_files, partial_files, git_toplevel

    Returns:
        List of plan dicts with keys: plan_type, priority, target_file, action, params, reason
    """
    plans = []
    seen_files = set()

    for clue in clues:
        if clue["clue_type"] != "missing_file":
            continue

        missing_path = clue["context"].get("file_path", "")
        if not missing_path:
            continue

        # Skip duplicates
        if missing_path in seen_files:
            continue
        seen_files.add(missing_path)

        filename = path_basename(missing_path)
        log("Looking for header: " + filename + " (include path: " + missing_path + ")")

        # Search deleted files for one that matches the include path
        for deleted_file in git_state["deleted_files"]:
            # Check if the deleted file ends with the missing include path
            if deleted_file.endswith(missing_path) or deleted_file.endswith("/" + missing_path):
                log("Found matching deleted file: " + deleted_file)
                plans.append({
                    "plan_type": "restore_file",
                    "priority": -1,  # Higher priority than built-in planner
                    "target_file": deleted_file,
                    "action": "restore_full",
                    "params": {"ref": git_state["ref"]},
                    "reason": "Restore " + deleted_file + " (needed for #include \"" + missing_path + "\")",
                })
                break

    return plans

"""
Partial File Restorer Planner Plugin

This plugin handles cases where a file exists but is corrupted or partially
deleted, causing type errors (unknown types, incomplete types, etc.).

When the detector finds type errors in a file that exists in the working
directory, this planner generates a plan to restore the full file from git.

Usage:
    Copy this file to .boil/plugins/planners/ in your repository.

Handles clue types:
    - unknown_type_name: "error: unknown type name 'foo'"
    - incomplete_type: "error: incomplete type 'struct foo'"
    - storage_size_unknown: "error: storage size of 'x' isn't known"
"""

def name():
    """Return the planner name for logging."""
    return "PartialFileRestorerPlanner"

def can_handle(clue_type):
    """Return True if this planner handles the given clue type."""
    return clue_type in [
        "unknown_type_name",
        "incomplete_type",
        "storage_size_unknown",
    ]

def plan(clues, git_state):
    """Generate repair plans from clues.

    Args:
        clues: List of dicts with keys: clue_type, confidence, context, source_line
        git_state: Dict with keys: ref, deleted_files, partial_files, git_toplevel

    Returns:
        List of plan dicts with keys: plan_type, priority, target_file, action, params, reason
    """
    plans = []
    files_to_restore = set()

    for clue in clues:
        if clue["clue_type"] not in ["unknown_type_name", "incomplete_type", "storage_size_unknown"]:
            continue

        # Extract file path from context (different detectors use different keys)
        context = clue["context"]
        file_path = context.get("file_path", context.get("file", ""))
        if not file_path:
            continue

        # Only restore if the file exists but is corrupted (partial file)
        if file_exists(file_path):
            files_to_restore.add(file_path)
            log("Found partially corrupted file: " + file_path)

    # Generate restore plans for each unique file
    for file_path in files_to_restore:
        # Verify git has the complete file
        git_content = git_show(file_path, git_state["ref"])
        if git_content:
            plans.append({
                "plan_type": "restore_file",
                "priority": 0,
                "target_file": file_path,
                "action": "restore_full",
                "params": {"ref": git_state["ref"]},
                "reason": "Restore partially corrupted file " + file_path + " (missing type definitions)",
            })

    return plans

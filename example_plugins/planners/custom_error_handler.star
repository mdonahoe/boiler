"""
Custom Error Handler Planner Plugin - Example Template

This is a template showing the structure of a Starlark planner plugin.
Copy and modify this file to handle custom error patterns in your project.

Usage:
    1. Copy this file to .boil/plugins/planners/ in your repository
    2. Modify name(), can_handle(), and plan() for your use case
    3. Add a matching detector plugin in .boil/plugins/detectors/ if needed

Available built-in functions:
    Git operations:
        git_show(path, ref="HEAD")     - Read file from git history
        git_grep(pattern, ref="HEAD")  - Search git history

    File system (read-only):
        file_exists(path)              - Check if file exists
        read_file(path)                - Read file contents
        list_dir(path)                 - List directory

    Pattern matching:
        regex_match(pattern, text)     - Match regex with named groups
        regex_find_all(pattern, text)  - Find all matches

    Path utilities:
        path_join(*parts)              - Join path components
        path_basename(path)            - Get filename
        path_dirname(path)             - Get directory
        path_ext(path)                 - Get extension

    Debugging:
        log(message)                   - Print when BOIL_VERBOSE=1
"""

def name():
    """Return the planner name for logging.

    This name appears in boil's verbose output and debug logs.
    """
    return "CustomErrorHandlerPlanner"

def can_handle(clue_type):
    """Return True if this planner handles the given clue type.

    Args:
        clue_type: String identifying the type of error clue

    Returns:
        bool: True if this planner can generate plans for this clue type
    """
    # Modify this list to match the clue types you want to handle
    return clue_type in ["custom_error_type"]

def plan(clues, git_state):
    """Generate repair plans from detected error clues.

    Args:
        clues: List of error clue dicts, each containing:
            - clue_type: String identifying the error type
            - confidence: Float from 0.0 to 1.0
            - context: Dict with extracted information (varies by detector)
            - source_line: The original error text that matched

        git_state: Dict containing:
            - ref: Git reference (usually "HEAD")
            - deleted_files: List of files deleted from working directory
            - partial_files: List of files that differ from git
            - git_toplevel: Root directory of git repository

    Returns:
        List of repair plan dicts, each containing:
            - plan_type: "restore_file" (currently the only supported type)
            - priority: Integer, lower = higher priority (executed first)
            - target_file: Path to the file to restore
            - action: "restore_full" or "restore_lines"
            - params: Dict with action-specific parameters
            - reason: Human-readable explanation for logs
    """
    plans = []

    for clue in clues:
        if clue["clue_type"] != "custom_error_type":
            continue

        # Extract information from the clue context
        # (the keys depend on your detector's named capture groups)
        file_path = clue["context"].get("file", "")
        if not file_path:
            continue

        log("Processing custom error for: " + file_path)

        # Check if the file needs to be restored
        if file_path in git_state["deleted_files"]:
            # File was completely deleted - restore it
            plans.append({
                "plan_type": "restore_file",
                "priority": 0,
                "target_file": file_path,
                "action": "restore_full",
                "params": {"ref": git_state["ref"]},
                "reason": "Restore deleted file: " + file_path,
            })
        elif file_exists(file_path):
            # File exists but may be corrupted - check git for differences
            git_content = git_show(file_path, git_state["ref"])
            current_content = read_file(file_path)
            if git_content and current_content != git_content:
                plans.append({
                    "plan_type": "restore_file",
                    "priority": 0,
                    "target_file": file_path,
                    "action": "restore_full",
                    "params": {"ref": git_state["ref"]},
                    "reason": "Restore corrupted file: " + file_path,
                })

    return plans

"""
Python Module Restorer Planner Plugin

Handles ModuleNotFoundError by restoring the missing module directory from git.
When Python can't import a module like 'src' or 'src.pipeline', this planner
finds all deleted files under that directory and restores them.

Usage:
    Copy this file to .boil/plugins/planners/ in your repository.
    Also copy the matching detector: python_module_not_found.json

Handles clue types:
    - module_not_found: From PythonModuleNotFoundDetector
"""

def name():
    return "PythonModuleRestorerPlanner"

def can_handle(clue_type):
    return clue_type == "module_not_found"

def plan(clues, git_state):
    plans = []
    restored_paths = set()

    # First, collect all modules we need to restore
    modules_to_restore = set()
    for clue in clues:
        if clue["clue_type"] != "module_not_found":
            continue
        module_name = clue["context"].get("module", "")
        if module_name:
            # Get the top-level module (e.g., "src" from "src.pipeline.handlers")
            top_module = module_name.split(".")[0]
            modules_to_restore.add(top_module)

    log("Modules to restore: " + str(list(modules_to_restore)))

    # Find all deleted files that belong to any of these modules
    for deleted_file in git_state["deleted_files"]:
        # Check if this file belongs to any module we need to restore
        for module in modules_to_restore:
            if deleted_file.startswith(module + "/") or deleted_file == module:
                if deleted_file not in restored_paths:
                    restored_paths.add(deleted_file)
                    plans.append({
                        "plan_type": "restore_file",
                        "priority": -5,  # High priority - modules are critical
                        "target_file": deleted_file,
                        "action": "restore_full",
                        "params": {"ref": git_state["ref"]},
                        "reason": "Restore " + deleted_file + " (part of missing module)",
                    })
                break

    log("Generated " + str(len(plans)) + " restore plans")
    return plans

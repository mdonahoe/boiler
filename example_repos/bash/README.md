# Bash Example Repository

This directory demonstrates boil on a complex C codebase: GNU Bash 5.3.

## Directory Structure

- `before/` - Full bash source (1606 files) - the starting point for boiling
- `after/` - Minimal buildable subset (372 files, 23% of original) - the result of boiling

## Running Boil

```bash
cd before/
boil --hard make test
```

The `--hard` flag deletes all tracked files first, then iteratively restores
only what's needed to make the build succeed.

## Custom Plugin

The bash build system uses make subdirectories (e.g., `builtins/`). When make
runs in a subdirectory, error messages reference relative paths like `./psize.sh`
instead of the full path `builtins/psize.sh`.

The built-in planners can't resolve these paths, so a custom Starlark plugin
handles this:

```
before/.boil/plugins/planners/make_directory_resolver.star
```

### How It Works

1. The `make_enter_directory` detector captures when make enters a subdirectory:
   ```
   make[1]: Entering directory '/path/to/builtins'
   ```

2. The `missing_file` detector captures the error:
   ```
   /bin/sh: ./psize.sh: No such file
   ```

3. The plugin's `plan()` function:
   - Finds the `make_enter_directory` clue to get the current directory
   - Converts the absolute path to a path relative to git toplevel
   - Resolves `./psize.sh` → `builtins/psize.sh`
   - Checks if that file exists in `git_state["deleted_files"]`
   - Returns a `restore_file` plan with priority -1 (higher than built-in)

### Plugin API

Starlark planners implement three functions:

```python
def name():
    """Return planner name for logging."""
    return "MyPlanner"

def can_handle(clue_type):
    """Return True if this planner handles the given clue type."""
    return clue_type in ["missing_file", "my_custom_error"]

def plan(clues, git_state):
    """Generate repair plans from clues.

    Args:
        clues: List of dicts with keys:
            - clue_type: string
            - confidence: float
            - context: dict of string -> string
            - source_line: string

        git_state: Dict with keys:
            - ref: string (git ref being restored from)
            - git_toplevel: string (absolute path to repo root)
            - deleted_files: list of strings (files deleted from ref)
            - partial_files: list of dicts with file, line_ratio, status

    Returns:
        List of plan dicts with keys:
            - plan_type: string (e.g., "restore_file")
            - priority: int (lower = higher priority, negative allowed)
            - target_file: string
            - action: string (e.g., "restore_full")
            - params: dict
            - reason: string
    """
    return []
```

Built-in functions available in plugins:
- `log(message)` - Print debug message (shown in verbose mode)
- `file_exists(path)` - Check if file exists
- `read_file(path)` - Read file contents
- `regex_match(pattern, text)` - Match regex pattern

## Results

| Metric | Before | After | Reduction |
|--------|--------|-------|-----------|
| Files | 1606 | 372 | 77% |
| Source lines | ~700K | ~190K | ~73% |

The `after/` directory compiles to a fully functional bash binary and passes tests.

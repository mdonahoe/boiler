# boiler

Automatically restore missing code from git history by iteratively running tests and fixing errors.

## What is boil.py?

When you delete code and tests fail, `boil.py` automatically restores only the code that's actually needed:

1. Runs your test command
2. Analyzes the error output using a pipeline of detectors
3. Generates repair plans (restore files, restore code elements, etc.)
4. Executes repairs and repeats until tests pass

This is useful for:
- Aggressively deleting unused code and seeing what actually breaks
- Minimizing dependencies by removing code and restoring only what's needed
- Tree-shaking your codebase to find dead code

## Installation

Make sure the `boil` script is on your PATH

Requirements:
- Python 3.x
- Git repository with history

## Basic Usage

```bash
# Basic: run until tests pass
boil make test

# Limit iterations (useful for testing)
boil -n 5 python3 test_my_code.py

# Use a different git reference
boil --ref HEAD~10 python3 -m pytest

# Abort and restore original state
boil --abort
```

## How It Works

1. **Creates a "boiling" branch**: All changes are tracked in a separate git branch
2. **Saves initial state**: Creates a `boil_start` commit with your current working directory
3. **Iterative fixing**:
   - Runs your test command
   - If it fails, analyzes the error using detectors (permission denied, missing files, missing Python code, etc.)
   - Creates repair plans (restore files, restore code, fix permissions, etc.)
   - Executes the highest-priority plan
   - Repeats until tests pass or iteration limit reached
4. **Stops when**: Tests pass OR iteration limit reached

## The Boiling Branch

Boil.py creates a branch called `boiling` to track its progress:
- Each fix attempt is a separate commit
- Inspect history: `git log boiling`
- Use `--abort` to clean up and restore original state
- If boiling succeeds, use `--clear` to just delete the .boil directory and `boiling` branch, leaving the working directory as-is.

## Command Line Options

- `-n <number>`: Maximum number of iterations (default: unlimited)
- `--ref <commit>`: Git reference to restore code from (default: HEAD)
- `--abort`: Abort current boiling session and restore working directory

## The Pipeline System

Boil.py uses a three-stage pipeline for error analysis and repair:

### Stage 1: Detection
Detectors analyze error output to identify issues:
- **PermissionDeniedDetector**: Permission errors
- **MakeMissingTargetDetector**: Missing make targets
- **MissingPythonCodeDetector**: Missing Python classes/functions/imports
- **FileNotFoundDetector**: Missing files (Python, shell, C compilation)

### Stage 2: Planning
Planners create repair strategies for each detected error:
- **PermissionFixPlanner**: Restore files with wrong permissions
- **MissingFilePlanner**: Restore deleted files
- **MakeMissingTargetPlanner**: Restore files missing from make
- **MissingPythonCodePlanner**: Restore missing code elements in existing files

### Stage 3: Execution
Executors perform the repairs:
- **GitRestoreExecutor**: Restore entire files from git
- **PythonCodeRestoreExecutor**: Restore specific Python code elements using src_repair

## Examples

### Example 1: Restore missing code

```bash
# Delete a function from a file
# Tests fail: "class TestClass not found"
# Boil.py detects the error, creates a plan, uses src_repair to restore just the class
boil python3 test_suite.py
```

### Example 2: Find dead code

```bash
# Delete a file
rm src/suspicious.py

# See if tests pass
boil python3 -m pytest

# If boil.py doesn't restore it, it was dead code!
```

## Tips

1. **Always commit a valid repo state before boiling**: boiler assumes that the ref commit is good, and the current working directory is bad. If your ref is also bad, the tests will never pass.
2. **Start small**: Use `-n 5` when testing to avoid long loops
3. **Check the boiling branch**: `git log boiling` shows what was restored
4. **Use --abort liberally**: Don't be afraid to abort and try again
5. **Check .boil/ directory**: Contains debug output from each iteration

## Troubleshooting

**Q: Boiling restored too much code**
A: Try `--abort` and be more specific with your deletions.

**Q: The boiling branch has weird commits**
A: This is normal. Each fix attempt is a separate commit.

**Q: Can I boil non-Python code?**
A: File-level restoration works on any language. Python code element restoration is Python-specific.

## C Code Support

Boiler can handle C compilation errors:

- **Implicit function declarations**: Detects missing project functions and creates forward declarations
- **Undeclared identifiers**: Restores missing function definitions from git
- **Linker undefined symbols**: Restores missing functions to the correct compilation target file

**Limitations**:
- Missing includes (stdlib headers) are detected but not automatically fixed
- Some errors (missing headers like `<fcntl.h>`, `<stdarg.h>`) are not (yet) fixed by src_repair
- File validation ensures repairs actually modify files (prevents infinite loops)

See `notes/c_error_handling_lessons.md` for detailed analysis.

## Known Issues

1. Named globals aren't supported and always get restored
2. Enum restoration makes __init__ functions appear
3. Missing C headers are not automatically added (requires future planner/executor)
4. Some stdlib functions may not be in the filtered list and will attempt restoration

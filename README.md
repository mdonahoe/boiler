# boiler

Automatically restore missing code from git history by iteratively running tests and fixing errors.

## What is `boil`?

When you delete code and tests fail, `boil` automatically restores only the code that's actually needed:

1. Runs your test command
2. Analyzes the error output using a pipeline of detectors
3. Generates repair plans (restore files, restore code elements, etc.)
4. Executes repairs and repeats until tests pass

This is useful for:
- Aggressively deleting unused code and seeing what actually breaks
- Minimizing dependencies by removing code and restoring only what's needed
- Tree-shaking your codebase to find dead code

## Installation

### Option 1: System-wide installation (recommended)

```bash
make install
```

This installs `boil` and `tree_print` to `/usr/local/bin` (requires sudo/root access).

To install to a different location:
```bash
make install PREFIX=/path/to/install
```

To uninstall:
```bash
make uninstall
```

### Option 2: Manual PATH setup

Make sure the `boil` binary is on your PATH.

### Option 3: Build from source

```bash
cd boiler
make
./boil --help
```

Requirements:
- Go 1.21+ (for building)
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

Boil creates a branch called `boiling` to track its progress:
- Each fix attempt is a separate commit
- Inspect history: `git log boiling`
- Use `--abort` to clean up and restore original state
- If boiling succeeds, use `--finish` to delete the .boil directory and `boiling` branch, leaving the working directory as-is.

## Command Line Options

- `-n <number>`: Maximum number of iterations (default: unlimited)
- `--ref <commit>`: Git reference to restore code from (default: HEAD)
- `--abort`: Abort current boiling session and restore working directory
- `--check`: Analyze current boil session and show status/statistics
- `--check --debug-iterations START-END`: Show detailed plan info for specific iterations

## The Pipeline System

Boil uses a three-stage pipeline for error analysis and repair, implemented in Go with JSON and Starlark configuration:

### Stage 1: Detection (JSON)
Detectors are defined in JSON files (`src/boil/detectors/definitions/*.json`) and match regex patterns against error output:
- **FileNotFoundDetector**: Missing files (Python, shell, etc.)
- **PermissionDeniedDetector**: Permission errors
- **MakeMissingTargetDetector**: Missing make targets
- **CLinkErrorDetector**: C linker undefined symbols
- **CImplicitDeclarationDetector**: Missing C function declarations
- **PythonNameErrorDetector**: Missing Python names/imports

### Stage 2: Planning (Go + Starlark)
Planners create repair strategies. Core planners are in Go (`src/boil/planners/*.go`), with plugin support via Starlark:
- **MissingFilePlanner**: Restore deleted files from git
- **PermissionFixPlanner**: Fix file permissions
- **MakeMissingTargetPlanner**: Restore files for make targets
- **LinkerUndefinedSymbolsPlanner**: Restore C functions for linker errors
- **MissingCFunctionPlanner**: Add missing C function definitions

### Stage 3: Execution (Go)
Executors perform the repairs:
- **restore_full**: Restore entire files from git history
- **restore_c_element**: Restore C code elements (functions, structs)
- **restore_python_element**: Restore Python code elements (classes, functions)

## Examples

### Example 1: Restore missing code

```bash
# Delete a function from a file
# Tests fail: "class TestClass not found"
# Boil detects the error, creates a plan, restores just the class
boil python3 test_suite.py
```

### Example 2: Find dead code

```bash
# Delete a file
rm src/suspicious.py

# See if tests pass
boil python3 -m pytest

# If boil doesn't restore it, it was dead code!
```

## Tips

1. **Always commit a valid repo state before boiling**: boiler assumes that the ref commit is good, and the current working directory is bad. If your ref is also bad, the tests will never pass.
2. **Start small**: Use `-n 5` when testing to avoid long loops
3. **Check the boiling branch**: `git log boiling` shows what was restored
4. **Use --abort liberally**: Don't be afraid to abort and try again
5. **Check session status**: Use `boil --check` to see what was fixed and what failed
6. **Check .boil/ directory**: Contains debug output from each iteration

## Troubleshooting

**Q: Boiling restored too much code**
A: Try `--abort` and be more specific with your deletions.

**Q: The boiling branch has weird commits**
A: This is normal. Each fix attempt is a separate commit.

**Q: Can I boil non-Python code?**
A: File-level restoration works on any language. Python code element restoration is Python-specific.

## Plugin System

Boil supports plugins for custom detectors and planners without modifying the core codebase. Plugins are loaded from `.boil/plugins/` in your repository:

```
your-repo/.boil/plugins/
├── detectors/     # JSON detector definitions
│   └── my_error.json
└── planners/      # Starlark planner scripts
    └── my_planner.star
```

**Detector plugins** (JSON): Define regex patterns to match error messages.

**Planner plugins** (Starlark): Write repair logic with access to git operations (`git_show`, `git_grep`), file system (`read_file`, `file_exists`), and pattern matching (`regex_match`).

See `AGENTS.md` for detailed plugin documentation.

## C Code Support

Boiler can handle C compilation errors:

- **Implicit function declarations**: Detects missing project functions and creates forward declarations
- **Undeclared identifiers**: Restores missing function definitions from git
- **Linker undefined symbols**: Restores missing functions to the correct compilation target file
- **Unknown type names**: Restores struct/typedef definitions from headers

**Limitations**:
- Missing stdlib includes (like `<fcntl.h>`) are detected but not automatically fixed
- File validation ensures repairs actually modify files (prevents infinite loops)

## Known Issues

1. Named globals aren't fully supported in Python element restoration
2. Missing C stdlib headers are not automatically added
3. Some stdlib functions may trigger false restoration attempts

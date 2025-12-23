# Boiler User Guide and Contribution Guide

## Table of Contents
- [Using Boil](#using-boil)
- [Contributing to Boiler](#contributing-to-boiler)
- [AI Agent Guide](#ai-agent-guide-for-fixing-boiler)
- [Plugin System](#plugin-system)

---

## Using Boil

**Boil** is an automated code restoration tool that iteratively runs your tests and fixes errors by restoring deleted or corrupted files from git history.

### Quick Start

```bash
# Basic usage: run boil with your test command
boil make test

# Specify number of iterations
boil -n 10 make test

# Delete all files first (hard mode)
boil --hard make test

# Clear a random file first (soft mode)
boil --soft make test
```

### Available Commands

#### Running Boil
- `boil <command>` - Run boil with your test command
- `boil -n <iterations> <command>` - Limit number of repair iterations
- `boil --hard <command>` - Delete all files before starting
- `boil --soft <command>` - Clear one random file before starting

#### Managing Sessions
- `boil --abort` - Abort current session and restore to pre-boil state
- `boil --finish` - Remove boiling session but keep current state
- `boil --check` - Analyze current session and show statistics
- `boil --debug-iterations <start>-<end>` - Debug specific iterations

#### Utilities
- `boil --identify-removable <files>` - Find unused functions that can be removed
- `boil --fix=claude [repo]` - Invoke Claude AI to fix boiler for unfixable errors
- `boil --test-detectors <error-file>` - Test all detectors on an error output
- `boil --handle-error <error-file>` - Test pipeline on a specific error

### How Boil Works

1. **Iteration Loop**: Boil runs your test command and captures output
2. **Error Detection**: Pipeline detectors analyze stderr/stdout for error patterns
3. **Planning**: Planners generate repair plans (what files to restore, what code to add)
4. **Execution**: Executors perform the repairs using git history
5. **Repeat**: Loop until tests pass or iteration limit reached

### Understanding .boil Directory

When boil runs, it creates a `.boil/` directory with debugging information:
- `iter*.pipeline.json` - Pipeline state for each iteration
- `iter*.exit*.txt` - Command output for each iteration
- JSON files contain detected clues, generated plans, and execution results

Use `boil --check` to analyze this data and see what boiler is doing.

---

## Contributing to Boiler - Issue Tracking

This project uses **bd (beads)** for issue tracking.

**Quick reference:**
- `bd ready` - Find unblocked work
- `bd create "Title" -d "longer description` - Create issue
- `bd close <id>` - Complete work
- `bd sync` - Sync with git (run at session end)

For full workflow details: `bd prime`

### Project Structure

```
boiler/
├── src/                      # Source code
│   ├── boil.py              # Main entry point
│   ├── pipeline/            # Error handling pipeline
│   │   ├── detectors/       # Error pattern detectors
│   │   ├── planners/        # Repair plan generators
│   │   └── executors/       # Repair executors
│   ├── legacy_handlers.py   # Legacy error handlers
│   └── *_repair.py          # Code restoration utilities
├── tests/                   # Test suite
├── example_repos/           # Test repositories
└── Makefile                 # Build and test commands
```

### Development Workflow

1. **Set up development environment**
```bash
cd ~/boiler
make check  # Fast checks (integrity + linting)
make test   # Full test suite (takes several minutes)
```

2. **Make changes**
   - Edit code in `src/`
   - Add tests in `tests/`
   - Follow existing patterns

3. **Test your changes**
```bash
make check  # Must pass before you call `boil` again.
make test   # All tests must pass before you commit, but it's ok to try `boil` something while these slower tests are broken.
```

4. **Commit**
```bash
git add <files>
git commit -m "Description"
git push
```

### Adding New Error Handlers

Boiler uses a pipeline architecture to handle errors. To add support for a new error type:

#### 1. Create a Detector

Detectors find error patterns in command output.

```python
# src/pipeline/detectors/my_error.py
from src.pipeline.detectors.base import Detector

class MyErrorDetector(Detector):
    PATTERNS = {
        "my_error_type": [
            r"error: cannot find file '(?P<file>[^']+)'",
        ]
    }

    EXAMPLES = [
        (
            "error: cannot find file 'foo.txt'",
            {"clue_type": "my_error_type", "file": "foo.txt"}
        )
    ]
```

Do NOT add other methods or overrides. There are tests to prevent this.

#### 2. Create a Planner

Planners generate repair plans from detected clues.

```python
# src/pipeline/planners/my_error.py
from src.pipeline.planners.base import Planner

class MyErrorPlanner(Planner):
    def can_handle(self, clue_type: str) -> bool:
        return clue_type == "my_error_type"

    def plan(self, clue: ErrorClue, git_state: GitState) -> List[RepairPlan]:
        # Generate plan to restore missing file
        return [RepairPlan(
            action="restore_full",
            target_file=clue.context["file"],
            source_ref=git_state.ref
        )]
```

Planners can read source files from the index or git and make restoration plans,
but a planner should NOT modify the working directory on it's own.
Rely on Executors for that.

#### 3. Register Components

```python
# src/pipeline/handlers.py
def register_all_handlers():
    # ... existing registrations ...
    register_detector(MyErrorDetector())
    register_planner(MyErrorPlanner())
```

#### 4. Add Tests

```python
# tests/test_my_error.py
class TestMyErrorDetector(unittest.TestCase):
    def test_detects_error(self):
        detector = MyErrorDetector()
        err = "error: cannot find file 'foo.txt'"
        clues = detector.detect(err, "")
        self.assertEqual(len(clues), 1)
        self.assertEqual(clues[0].clue_type, "my_error_type")
```

### Critical Rules for Contributors

#### Test Integrity

**NEVER modify tests to make them pass. Fix your implementation instead.**

If `make check` fails:
1. Read the error message - it tells you what's wrong
2. Fix the IMPLEMENTATION code, NOT the test
3. Commit test changes separately BEFORE implementation changes

Common failures:
- `INTEGRITY CHECK FAILED` - You modified tests. Revert and fix code.
- `HARD-CODED LIBRARY KEYWORDS` - Make your planner generic using git history
- `Detected inefficient regex` - Rewrite pattern to avoid exponential backtracking

#### Writing Generic Planners

Planners must work for ANY codebase, not just specific libraries.

**❌ BAD (Hard-coded):**
```python
TYPE_TO_HEADER = {
    "TSLanguage": "tree-sitter/lib/include/tree_sitter/api.h"
}
if type_name in TYPE_TO_HEADER:
    return TYPE_TO_HEADER[type_name]
```

**✅ GOOD (Generic):**
```python
# Use git history to find where types are defined
result = subprocess.run(
    ['git', 'grep', type_name, 'HEAD', '--', '*.h'],
    capture_output=True, text=True
)
headers = parse_git_grep_output(result.stdout)
```

#### Session Completion Protocol

**When ending a work session**, you MUST:

1. Create issues for remaining work
2. Run `make check` and `make test` (if code changed)
3. Close or update issues with `bd`
4. **PUSH TO REMOTE** (MANDATORY):
   ```bash
   git pull --rebase
   bd sync
   git push
   git status  # Must show "up to date with origin"
   ```

Work is NOT complete until `git push` succeeds.

### Using the Fix-with-Claude Script

If boiler can't handle an error, you can invoke Claude AI to help:

```bash
# From the broken repo
boil --fix=claude
```

This analyzes `.boil/` debug output and asks Claude to add new detectors/planners to boiler.

---

## AI Agent Guide (For Fixing Boiler)

This section is for AI agents (like Claude) that are helping improve boiler when it encounters unfixable errors.

### Quick Reference

```bash
# Analyze current boiling session
boil --check

# Test a specific error
boil --handle-error ~/.boil/iter1.exit1.txt

# Run tests
make check  # Fast
make test   # Full suite

# Reset to pre-boil state (for testing)
boil --abort
```

### Understanding the Task

When a user runs `boil --fix=claude`, they're asking you to:
1. Analyze debugging information in `[repo]/.boil/`
2. Understand what error boiler couldn't handle
3. Add new detectors/planners in `~/boiler/src/pipeline/`
4. Ensure changes work generically for ANY codebase

### Analysis Steps

1. **Check session status**
```bash
cd /path/to/broken/repo
boil --check  # Summary
ls .boil/     # See all debug files
```

2. **Read pipeline JSON files**
   - `iter*.pipeline.json` - See what boiler tried to do
   - Look for:
     - Undetected errors (no clues found)
     - Missing planners (clues but no plans)
     - Failed executions
     - Infinite loops (same error repeated)

3. **Understand the error pattern**
   - What does the error look like?
   - What file needs fixing?
   - What should the fix be?

### Creating Pipeline Components

Follow the [Adding New Error Handlers](#adding-new-error-handlers) section above.

**Key principles:**
- Detectors extract information from error text
- Planners decide what to fix
- Executors perform the fix
- Everything must be generic (work for any codebase)

### Testing Your Changes

```bash
# In ~/boiler
make check  # Must pass
make test   # All tests must pass

# In the broken repo
boil --abort  # Reset to broken state
boil make test  # Try your fix

# If it works but you want to test again
boil --abort  # Returns to broken state
```

### Common Pitfalls

1. **Hard-coding library names** - Use git history instead
2. **Modifying tests** - Fix implementation, not tests
3. **Not validating repairs** - Executors must verify changes happened
4. **Assuming file contents** - Check git history for actual code
5. **Skipping `make test`** - Fast checks miss edge cases

### Session Completion

When you're done:
1. Ensure `make check` and `make test` pass
2. Test on the broken repo (`boil --abort` then `boil make test`)
3. Commit changes with clear messages
4. **Push to remote** (see [Session Completion Protocol](#session-completion-protocol))

**CRITICAL**: Work is NOT complete until `git push` succeeds.

---

## Plugin System

Boil supports plugins that let you add custom detectors and planners to a specific repository without modifying the boiler codebase. This is useful when AI agents need to handle repo-specific error patterns.

### Plugin Location

Plugins are loaded from `.boil/plugins/` in the current working directory:

```
your-repo/
├── .boil/
│   └── plugins/
│       ├── detectors/     # JSON detector definitions
│       │   └── my_error.json
│       └── planners/      # Starlark planner scripts
│           └── my_planner.star
```

### Detector Plugins (JSON)

Detectors are data-driven and defined in JSON. They match error patterns and extract context.

**Example:** `.boil/plugins/detectors/my_error.json`
```json
{
  "name": "MyErrorDetector",
  "priority": 100,
  "patterns": {
    "my_custom_error": "custom error: (?P<message>.+) in (?P<file>.+)"
  },
  "examples": [
    {
      "name": "my_custom_error",
      "input": "custom error: something failed in foo.txt",
      "clue_type": "my_custom_error",
      "context": {"message": "something failed", "file": "foo.txt"}
    }
  ]
}
```

**Fields:**
- `name`: Detector name (for logging)
- `priority`: Execution order (lower = earlier, default 100)
- `patterns`: Map of clue_type to regex pattern (use named groups like `(?P<name>...)`)
- `examples`: Test cases to verify the pattern works

### Planner Plugins (Starlark)

Planners contain logic and are written in Starlark (a Python-like language). They receive detected clues and generate repair plans.

**Example:** `.boil/plugins/planners/my_planner.star`
```python
def name():
    """Return the planner name."""
    return "MyCustomPlanner"

def can_handle(clue_type):
    """Return True if this planner handles the given clue type."""
    return clue_type == "my_custom_error"

def plan(clues, git_state):
    """Generate repair plans from clues.

    Args:
        clues: List of dicts with keys: clue_type, confidence, context, source_line
        git_state: Dict with keys: ref, deleted_files, partial_files, git_toplevel

    Returns:
        List of plan dicts with keys: plan_type, priority, target_file, action, params, reason
    """
    plans = []
    for clue in clues:
        if clue["clue_type"] != "my_custom_error":
            continue

        file_path = clue["context"]["file"]

        # Check if file was deleted
        if file_path in git_state["deleted_files"]:
            plans.append({
                "plan_type": "restore_file",
                "priority": 0,
                "target_file": file_path,
                "action": "restore_full",
                "params": {"ref": git_state["ref"]},
                "reason": "Restore " + file_path + " for: " + clue["context"]["message"],
            })

    return plans
```

### Available Built-in Functions

Starlark planners have access to these built-in functions:

#### Git Operations
```python
git_show(path, ref="HEAD")     # Read file content from git history
                                # Returns: str or None if not found

git_grep(pattern, ref="HEAD")  # Search git history for pattern
                                # Returns: [(file, line_num, content), ...]
```

#### File System (read-only)
```python
file_exists(path)              # Check if file exists in working dir
                                # Returns: bool

read_file(path)                # Read file from working dir
                                # Returns: str or None if not found

list_dir(path)                 # List directory contents
                                # Returns: [filename, ...]
```

#### Pattern Matching
```python
regex_match(pattern, text)     # Match regex with named groups
                                # Returns: {"full": str, "groups": {name: value}} or None

regex_find_all(pattern, text)  # Find all matches
                                # Returns: [{"full": str, "groups": {...}}, ...]
```

#### Path Utilities
```python
path_join(*parts)              # Join path components
path_basename(path)            # Get filename from path
path_dirname(path)             # Get directory from path
path_ext(path)                 # Get file extension (e.g., ".c")
```

#### Debugging
```python
log(message)                   # Print message (when BOIL_VERBOSE=1)
```

### Example: Complex Planner

Here's a more complete example that searches git history:

```python
def name():
    return "MissingSymbolPlanner"

def can_handle(clue_type):
    return clue_type == "undefined_symbol"

def plan(clues, git_state):
    plans = []

    for clue in clues:
        if clue["clue_type"] != "undefined_symbol":
            continue

        symbol = clue["context"]["symbol"]

        # Search git history for where this symbol is defined
        matches = git_grep(symbol + r"\s*\(", git_state["ref"])

        for file, line, content in matches:
            # Check if this file was deleted
            if file in git_state["deleted_files"]:
                # Read the file to verify it contains the definition
                file_content = git_show(file, git_state["ref"])
                if file_content and contains_definition(file_content, symbol):
                    plans.append({
                        "plan_type": "restore_file",
                        "priority": 0,
                        "target_file": file,
                        "action": "restore_full",
                        "params": {"ref": git_state["ref"]},
                        "reason": "Restore " + file + " (defines " + symbol + ")",
                    })
                    break  # Only restore one file per symbol

    return plans

def contains_definition(content, symbol):
    """Check if content contains a function definition for symbol."""
    match = regex_match(symbol + r"\s*\([^)]*\)\s*\{", content)
    return match != None
```

### Disabling Plugins

To temporarily disable a plugin, prefix the filename with underscore:
- `_my_detector.json` - disabled
- `_my_planner.star` - disabled

### Testing Plugins

Test your plugins by running boil with verbose output:

```bash
BOIL_VERBOSE=1 boil make test
```

This will show which plugins are loaded and what clues/plans they generate.

---

## Additional Resources

- `README.md` - Project overview and quick start
- `tests/` - Examples of how to test components
- `example_repos/` - Test cases for different error types
- `.boil/` - Debug output from boiling sessions
- `docs/plugin-system-plan.md` - Detailed plugin system design

## Landing the Plane (Session Completion)

**When ending a work session**, you MUST complete ALL steps below. Work is NOT complete until `git push` succeeds.

**MANDATORY WORKFLOW:**

1. **File issues for remaining work** - Create issues for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **PUSH TO REMOTE** - This is MANDATORY:
   ```bash
   git pull --rebase
   bd sync
   git push
   git status  # MUST show "up to date with origin"
   ```
5. **Clean up** - Clear stashes, prune remote branches
6. **Verify** - All changes committed AND pushed
7. **Hand off** - Provide context for next session

**CRITICAL RULES:**
- Work is NOT complete until `git push` succeeds
- NEVER stop before pushing - that leaves work stranded locally
- NEVER say "ready to push when you are" - YOU must push
- If push fails, resolve and retry until it succeeds

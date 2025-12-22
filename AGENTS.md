# Boiler User Guide and Contribution Guide

## Table of Contents
- [Using Boil](#using-boil)
- [Contributing to Boiler](#contributing-to-boiler)
- [AI Agent Guide](#ai-agent-guide-for-fixing-boiler)

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

## Contributing to Boiler

Use `bd ready` to see the list of open issues ready to be worked on.
Use `bd create "title" -d "longer description"` to add issues for someone to do later.
Run `bd quickstart` to learn more about `bd`

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

## Additional Resources

- `README.md` - Project overview and quick start
- `tests/` - Examples of how to test components
- `example_repos/` - Test cases for different error types
- `.boil/` - Debug output from boiling sessions

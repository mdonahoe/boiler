# boiler

Automatically restore missing code from git history by iteratively running tests and fixing errors.

## What is boil.py?

`boil.py` helps you restore deleted code by "boiling" it back to life. When you delete code and tests fail, boil.py:
1. Runs your test command
2. Analyzes the error output
3. Restores only the necessary code from git history
4. Repeats until tests pass

This is useful for:
- Aggressively deleting unused code and seeing what actually breaks
- Minimizing dependencies by removing code and restoring only what's needed
- "Tree-shaking" your codebase to find dead code

## Installation

No installation needed. Just have `boil.py` and `py_repair.py` in your directory.

Requirements:
- Python 3.x
- Git repository with history

## Basic Usage

```bash
# Basic: run until tests pass
python3 boil.py python3 test_my_code.py

# Limit iterations (useful for testing)
python3 boil.py -n 5 python3 test_my_code.py

# Use a different git reference
python3 boil.py --ref HEAD~10 python3 test_my_code.py

# Abort and restore original state
python3 boil.py --abort
```

## How It Works

1. **Creates a "boiling" branch**: All changes are tracked in a separate git branch
2. **Saves initial state**: Creates a `boil_start` commit with your current working directory
3. **Iterative fixing**:
   - Runs your test command
   - If it fails, analyzes the error (NameError, ImportError, etc.)
   - Uses `py_repair.py` to restore missing code from git history
   - Commits the fix to the boiling branch
   - Repeats
4. **Stops when**: Tests pass OR iteration limit reached

## The Boiling Branch

Boil.py creates a branch called `boiling` to track its progress:
- Each fix attempt is a separate commit
- You can inspect the history: `git log boiling`
- The branch persists after boiling completes
- Use `--abort` to clean up and restore original state

## Command Line Options

- `-n <number>`: Maximum number of iterations (default: unlimited)
- `--ref <commit>`: Git reference to restore code from (default: HEAD)
- `--abort`: Abort current boiling session and restore working directory

## Examples

### Example 1: Delete code and restore what's needed

```bash
# Delete a bunch of code
rm src/unused.py
git diff > my_deletions.patch

# Try to boil it back
python3 boil.py -n 10 python3 -m pytest tests/

# If it works, commit the minimal changes
# If it doesn't, use --abort and try a different approach
```

### Example 2: Find dead code

```bash
# Delete suspicious code
rm src/maybe_unused.py

# See if tests pass
python3 boil.py python3 -m pytest

# If boil.py doesn't restore it, it was dead code!
```

### Example 3: Minimize dependencies

```bash
# Remove an entire module
git rm -r src/big_dependency/

# Restore only what's actually used
python3 boil.py -n 50 python3 test_suite.py
```

## Understanding Iterations

The `-n` parameter limits total iterations, not just fix attempts.

- Iteration 1: Run test → fails → apply fix
- Iteration 2: Run test → check if fix worked
- Iteration 3: Run test again if still failing → apply another fix
- etc.

**Important**: Always use `-n` ≥ 2 to allow boil.py to verify its fixes worked!

## Aborting a Session

If boiling goes wrong or you want to start over:

```bash
python3 boil.py --abort
```

This will:
1. Find the `boil_start` commit (your original state)
2. Reset your working directory to before boiling started
3. Delete the boiling branch
4. Clean up the `.boil` directory

## Error Handlers

Boil.py includes handlers for common Python errors:
- `NameError`: Restores missing class/function definitions
- `ImportError`: Restores missing modules
- `IndentationError`: Restores missing class definitions for orphaned methods
- `AttributeError`: Restores missing class methods
- `ModuleNotFoundError`: Restores missing packages
- And more...

## How py_repair.py Works

`py_repair.py` is the core restoration engine:
1. Analyzes your current code to see what's allowed (existing classes, functions, imports)
2. Fetches the git version of a file
3. Adds the missing item (e.g., "class Dog") to the allowed list
4. Filters the git version to include only allowed items
5. Writes the filtered result back to disk

This ensures only necessary code is restored, not everything from history.

## Tips

1. **Start small**: Use `-n 5` when testing to avoid infinite loops
2. **Check the boiling branch**: `git log boiling` shows what was restored
3. **Use --abort liberally**: Don't be afraid to abort and try again
4. **Commit before boiling**: Have a clean git state before starting
5. **Check .boil/ directory**: Contains error output from each iteration

## Known Issues

1. Restoring "name 'T' is not defined" will restore anything with a T in it
2. Restoring enum will make __init__ functions appear
3. Named globals aren't supported and thus always get restored

## TODO

1. Get more test code and have something that deletes random lines from it. Can boil fix it?
2. Add .h/.c support instead of just .py
3. If boiler knows the filetype and can parse the file, it can do a partial restore. Otherwise, it must do full restore
4. Research "tree-shaking" techniques

## Troubleshooting

**Q: Boil.py says "failed to fix" but tests actually pass**
A: You probably used `-n1`. The test passed but there wasn't another iteration to verify. Use `-n2` or higher.

**Q: Boil.py restored too much code**
A: Try `--abort` and be more specific with your deletions, or adjust the handlers in boil.py.

**Q: The boiling branch has weird commits**
A: This is normal. Each fix attempt is a separate commit. Use `git log boiling` to inspect.

**Q: Can I use boil.py on non-Python code?**
A: Currently only Python is fully supported. The error handlers are Python-specific.

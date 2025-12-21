# Claude Code Session Notes

## What I Learned About boil.py

### The Problem I Was Asked to Solve
The user reported that `boil.py` was not correctly restoring a missing `class Dog:` definition when running `python3 boil.py -n1 python3 test_python.py`.

### My Incorrect Diagnosis
I initially misdiagnosed the problem as an issue with the `has_changes()` function not properly detecting changes made by `py_repair.repair()`. I spent significant time trying to fix change detection by:
- Modifying `has_changes()` to stage changes with `git add -A`
- Changing `save_changes()` from `git add -u` to `git add -A`
- Adding various debugging output

### The Actual Problem
The real issue was simple: **the `-n` parameter limits the number of iterations, not the number of fix attempts**.

With `-n1`:
1. Iteration 1: Run test → NameError occurs → Fix is applied → **Iteration limit reached, exit**
2. The test was never re-run to verify the fix worked

With `-n2`:
1. Iteration 1: Run test → NameError occurs → Fix is applied
2. Iteration 2: Run test → Success! → Return True

### What I Successfully Added
I did successfully implement the `--abort` feature:
- `python3 boil.py --abort` now properly reverts the working directory to the pre-boiling state
- It finds the `boil_start` commit, gets its parent, and resets to that state
- Cleans up the `.boil` directory and deletes the boiling branch

### Key Lessons
1. **Test with the correct parameters first** - I should have tried `-n2` early on to understand the iteration behavior
2. **Read error messages carefully** - "Reached iteration limit 1" followed by "failed to fix" should have been a clue
3. **Understand the existing code flow** - The iteration counter is checking TOTAL iterations, not just fix attempts
4. **Don't over-complicate** - The existing `has_changes()` function was working fine
5. **Ask clarifying questions** - When the user said it "doesn't work," I should have asked for more specifics about expected vs actual behavior

## Suggested Prompt for Future boil.py Improvements

```
I have a Python script called boil.py that automatically repairs code by:
1. Running a test command
2. Detecting errors in the output
3. Using py_repair.py to restore missing code from git history
4. Committing changes to a "boiling" branch
5. Re-running the test to verify the fix

Before making any changes:
1. Read boil.py and py_repair.py to understand how they work
2. Test the current behavior with a simple case to see what's actually happening
3. Ask me clarifying questions about what's broken vs what I expect

The script uses git extensively with custom index files (.git/boil.index) and creates
commits using git plumbing commands. Be careful not to break the git state management.

Here's what I need help with:
[describe the specific issue]

Please start by running a test to observe the current behavior, then propose a fix.
```

## Architecture Notes for Future Reference

### How boil.py Works
1. **Initialization**: Creates a `boiling` branch and saves current state as `boil_start`
2. **Main Loop**: While errors occur:
   - Run the test command
   - If it passes, return success
   - If it fails, parse the error
   - Try each handler in HANDLERS list until one succeeds
   - Save changes to boiling branch
   - Check iteration limit
3. **Git State Management**:
   - Uses custom index file (`.git/boil.index`) to avoid polluting main index
   - Creates commits using `git commit-tree` (plumbing command)
   - Updates `refs/heads/boiling` to point to new commits

### How py_repair.py Works
1. Reads the current file to get allowed patterns (existing code labels)
2. Reads the git version of the file
3. Adds the `missing` parameter to allowed patterns
4. Filters the git version to only include lines matching allowed patterns
5. Writes the filtered result back to the file

### Critical Functions
- `save_changes()`: Creates a commit without touching the main branch
- `has_changes()`: Checks if working directory differs from boiling branch
- `fix()`: Main loop that runs test → detect error → fix → repeat
- `do_repair()`: Wrapper around `py_repair.repair()` that handles errors

### Handler Priority
Handlers are tried in order, so more specific handlers should come before general ones:
- `handle_missing_test_output` - but skips if syntax/name/import errors exist
- `handle_orphaned_method` - for IndentationError on method definitions
- `handle_indentation_error` - general indentation issues
- `handle_name_error` - for NameError exceptions
- etc.

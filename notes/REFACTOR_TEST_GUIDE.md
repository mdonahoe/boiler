# Using Example Repo Tests During Pipeline Refactor

## Purpose
You're about to refactor the pipeline system. This guide explains how to use the example repo tests to validate that your changes don't break core functionality.

## Quick Start
Before and after each major refactor step, run:
```bash
# Full test suite (includes example repos)
make test

# Just the example repo tests
python3 -m unittest tests.test_example_repos -v

# The 'simple' repo is the fastest to run.
python3 tests/test_example_repos.py ExampleRepoTest.test_simple_repo_boiling

```

## What These Tests Validate

### test_example_repos.py
Validates end-to-end boiler functionality:
1. Copies `before/` content to temp git repo
2. Deletes all files
3. Runs boiler to restore them
4. Verifies `make test` passes
5. Validates restored content matches `after/` expectations

**Failure here indicates a real problem with your refactored code.**

## Refactoring Strategy

### Phase 1: Establish Baseline
```bash
# Make sure all tests pass before you start
python3 -m unittest tests.test_example_repos -v
```

### Phase 2: Refactor in Small Steps
After each logical change:
```bash
python3 -m unittest tests.test_example_repos.ExampleReposTest.test_simple_repo_boiling -v
```
Use `simple` for quick iteration (it's much faster than the `dim` repo).

### Phase 3: Validate Full Suite
Before declaring success:
```bash
make test
```
## Interpreting Test Failures

### Problem: test_simple_repo_boiling fails
The boiler couldn't restore files or restore produced incorrect content.

**Check:**
1. Do handlers still register correctly after your changes?
2. Did you change how detectors work?
3. Did you change how planners generate solutions?
4. Did you change how executors apply fixes?

Run with verbose output to see pipeline logs:
```bash
python3 -m unittest tests.test_example_repos.ExampleReposTest.test_simple_repo_boiling -v
```

### Problem: Clear error showing missing file
Example output:
```
======================================================================
[simple] FILE IN after/ NOT FOUND IN BOILED RESULT
======================================================================
File: simple.c

Files in after/:
  - Makefile
  - simple.c
  - simple.py

Files in boiled result:
  - Makefile
  - simple.py
======================================================================
```

This means your refactor broke something that prevents `simple.c` from being restored.

### Problem: Clear error showing missing line
Example output:
```
======================================================================
[simple] LINE IN after/ NOT FOUND IN BOILED RESULT
======================================================================
File: simple.c
Problem at line 2 in after/:
  
after/simple.c:
    1: #include <stdio.h>
    2:  <-- MISSING FROM BOILED
    3: int main(void) {
...
```

The boiler is restoring the file but not with correct content.

## Important Notes

### Don't Skip the Subset Test
Run `test_after_is_subset.py` first to ensure fixtures are valid:
```bash
python3 -m unittest tests.test_after_is_subset -v
```

This prevents false positives (fixture problems misdiagnosed as code problems).

### Don't Modify Example Repos During Refactor

DO NOT EDIT ANYTHING IN THE `example_repos` FOLDER!!!
The user has prepped these intentionally to ensure your refactor is safe.

Keep `example_repos/simple/before` and `example_repos/simple/after` unchanged. They're your ground truth.
Same for `example_repos/dim/`

If you think they're wrong, document it and alert the user.

### The Tests are Slow
Each test spawns a git repo and runs boiler, so they can take a minute on larger repos, like dim.

- Use `test_simple_repo_boiling` for quick iteration
- Use `make test` as your final validation before submitting changes

## Success Criteria
After your refactor:
- ✅ `test_after_is_subset` passes (fixtures are valid)
- ✅ `test_simple_repo_boiling` passes (basic boiling works)
- ✅ `test_dim_repo_boiling` fails in the same way it failed before (no new regressions)
- ✅ `make test` passes (full test suite clean)

## When in Doubt
1. Run the simple test in isolation
2. Look at the structured error output
3. Check which component the test output indicates is failing
4. Narrow down to the specific handler/planner/executor
5. Use the detailed failure message to guide your fix

Good luck with the refactor!

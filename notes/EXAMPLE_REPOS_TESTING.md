# Example Repos Testing Framework

## Overview
Created a comprehensive testing framework for validating boiler's ability to restore deleted files in example repositories. The framework enforces that `after/` folders represent valid transformations of `before/` folders (deletions only).

## Key Learnings

### 1. Example Repo Structure
- Each repo in `example_repos/` has two folders:
  - `before/`: Complete source code that gets committed to git
  - `after/`: Expected state after boiler processes the repo (should be a subset of `before/`)
- Example: `example_repos/simple/` and `example_repos/dim/`

### 2. Strict Subset Validation
Created `tests/test_after_is_subset.py` that enforces:
- `after/` cannot have files that don't exist in `before/`
- Each file in `after/` must have same or fewer lines than in `before/`
- Lines must appear in the same order (no reordering, only deletions)
- This prevents invalid test fixtures

### 3. End-to-End Testing
Created `tests/test_example_repos.py` that:
- Tests each example repo by simulating the full boiler workflow
- Initializes git repo with `before/` content
- Deletes all files
- Runs boiler to restore them
- Verifies restoration succeeded with `make test`
- Validates boiled result matches `after/` folder expectations

### 4. Output Formatting
Key insight: **Clear, structured error output is critical for debugging test failures**

Instead of:
```
AssertionError: False is not true : [simple] File exists in after/ but not in before/: simple
```

Use structured output with visual separators:
```
======================================================================
[simple] EXTRA FILE IN after/ THAT DOESN'T EXIST IN before/
======================================================================
File: simple

Files in before/:
  - Makefile
  - simple.c
  - simple.py

Files in after/:
  - Makefile
  - simple <-- EXTRA
  - simple.c
  - simple.py
======================================================================
```

Benefits:
- Immediate visual clarity on what failed
- Side-by-side file comparisons
- Line-by-line content diffs for files
- Section dividers for readability

### 5. Refactoring Pattern
Converted from repo-specific test cases to parameterized approach:
```python
def test_simple_repo_boiling(self):
    self._test_repo_boiling("simple")

def test_dim_repo_boiling(self):
    self._test_repo_boiling("dim")

def _test_repo_boiling(self, repo_name):
    # Shared logic for all repos
```

This makes it easy to add new example repos without duplicating code.

### 6. Content Validation After Boiling
The test validates that post-boil state matches `after/` folder by:
- Checking all files in `after/` exist in boiled result
- Checking file contents match line-by-line in same order
- Allowing boiled result to have additional content (as long as `after/` is a subset)

## Files Modified
- `tests/test_after_is_subset.py` (created) - Validates example repo structure
- `tests/test_example_repos.py` (refactored) - End-to-end boiler tests
- `example_repos/dim/before/` (created) - Added dim as example repo

## Usage
Run the tests:
```bash
# Test example repo structure validation
python3 -m unittest tests.test_after_is_subset -v

# Test end-to-end boiling
python3 -m unittest tests.test_example_repos -v

# Or via make
make test
```

## Future Considerations
- Add more example repos to increase test coverage
- Consider extracting shared file comparison logic into utility module
- Could use same subset validation for other test scenarios

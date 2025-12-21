# Planner Validation Fix - Preventing Useless Plans

## Problem

The planner was creating restoration plans for files that **already existed and matched git**, leading to:
1. Wasted iterations attempting useless restorations
2. Executor validation catching it (good) but only after generating the plan
3. Pipeline reporting "no plans available" when it should have detected this earlier

### Example

```
Error: fatal error: ex.h: No such file or directory
File status: ex.h exists and matches HEAD
Planner: Creates plan to restore ex.h ❌ (wrong!)
Executor: Validates and rejects plan ✓ (but too late)
Result: Wasted iteration
```

## Root Cause

`MissingFilePlanner.plan()` didn't check if the file actually needed restoration:

```python
# OLD CODE - blindly creates plan
def plan(self, clue: ErrorClue, git_state: GitState) -> List[RepairPlan]:
    file_path = clue.context.get("file_path")

    return [RepairPlan(  # Always creates plan!
        target_file=file_path,
        action="restore_full",
        ...
    )]
```

## Solution

Added **file existence and git comparison check** to the planner:

```python
# NEW CODE - checks before planning
def plan(self, clue: ErrorClue, git_state: GitState) -> List[RepairPlan]:
    file_path = clue.context.get("file_path")

    # Check if file actually exists and matches git
    if os.path.exists(file_path):
        # Compare with git version
        diff_result = subprocess.run(
            ["git", "diff", "--quiet", git_state.ref, "--", git_relative_path],
            ...
        )

        if diff_result.returncode == 0:
            # File already matches git - no plan needed
            print(f"[Planner] {file_path} already exists and matches git, skipping")
            return []  # Don't create useless plan

    return [RepairPlan(...)]  # Only create plan if needed
```

## Defense in Depth

Now we have **3 layers of validation**:

### Layer 1: Planner (NEW)
- Checks if file exists
- Checks if file matches git version
- **Prevents** plan creation for already-restored files

### Layer 2: Executor Validation
- Validates plan before execution
- Checks if file exists in git
- **Rejects** invalid plans before attempting

### Layer 3: Executor Post-Check
- Verifies restoration created changes
- Checks file differs from boiling branch
- **Detects** when restoration didn't help

## Benefits

### Before
```
Iteration N: Detect "ex.h missing"
            → Create plan to restore ex.h
            → Executor validates: file already matches git
            → Executor rejects plan
            → No plans succeeded
            → Fall back to legacy handler
            → Legacy handler also fails
            → Report error
```

### After
```
Iteration N: Detect "ex.h missing"
            → Planner checks: file already matches git
            → Skip plan creation
            → No plans generated
            → Fall back to legacy handler immediately
            → Legacy handler handles it
```

**Result**: Skip the useless iteration where we try to restore a file that's already correct.

## Why Both Planner and Executor Checks?

**Planner check**: Prevents creating plans we know won't work
- Fast (just file stat + git diff)
- Happens early in the pipeline
- Saves executor work

**Executor check**: Safety net for edge cases
- File might be deleted between planning and execution
- File might exist but not in git
- Covers cases planner can't predict

## Testing

Created `test_planner_validation.py`:

### Test 1: Skip Already-Restored File
```
Error: test.py: No such file or directory
File exists: ✓
File matches git: ✓
Plans generated: 0 ✓
Result: PASS
```

### Test 2: Create Plan For Actually Missing File
```
Error: nonexistent123.txt: No such file
File exists: ✗
Plans generated: 1 ✓
Result: PASS
```

## What This Fixes

### Case 1: Misleading Error Messages
When a compiler says "can't find ex.h" but `ex.h` exists:
- **Old**: Try to restore ex.h, fail, waste iteration
- **New**: Skip restoration, fall back to legacy immediately

### Case 2: Already-Restored Files
When boil.py tries the same fix multiple times:
- **Old**: Keep creating plans to restore the same file
- **New**: Detect file is already restored, skip plan

### Case 3: Include Path Issues
When the real problem is include paths, not missing files:
- **Old**: Loop trying to restore a file that's already there
- **New**: Skip useless restoration, let legacy handler investigate

## Files Modified

- `pipeline/planners/file_restore.py` - Added validation to `MissingFilePlanner.plan()`
- `test_planner_validation.py` - Test suite
- `PLANNER_VALIDATION_FIX.md` - This document

## Performance Impact

**Minimal**: Just one extra file check + git diff per plan
**Benefit**: Avoids entire useless iterations

## Related Fixes

This complements the executor validation fix:
- **Executor fix**: Prevents claiming success when nothing changed
- **Planner fix**: Prevents creating plans that won't work

Together, they prevent infinite loops and wasted iterations.

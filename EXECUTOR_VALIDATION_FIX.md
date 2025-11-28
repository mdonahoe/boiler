# Executor Validation Fix - Preventing Infinite Loops

## Problem

The pipeline was looping infinitely, attempting the same restoration over and over without making progress.

### Root Cause

The `GitRestoreExecutor` was returning `success=True` even when:
1. The file already existed and matched the git version
2. The restoration didn't create any actual changes
3. The file was restored to a location that didn't help solve the error

This caused `boil.py` to think the fix worked, but the same error would reappear on the next iteration.

### Example Loop

```
Iteration 7: Restore ex.h → success=True, files_modified=["ex.h"]
Iteration 8: Same error → Restore ex.h → success=True, files_modified=["ex.h"]
Iteration 9: Same error → Restore ex.h → success=True, files_modified=["ex.h"]
...infinite loop...
```

## Solution

Added **three validation checks** to the executor:

### 1. Pre-Execution Check: File Already Matches

```python
if os.path.exists(file_path):
    # Compare with git version
    show_result = subprocess.run(
        ["git", "diff", "--quiet", ref, "--", git_relative_path],
        cwd=git_toplevel,
        capture_output=True
    )
    if show_result.returncode == 0:
        # File already matches git version - nothing to do
        return RepairResult(
            success=False,
            error_message=f"File {file_path} already matches git version"
        )
```

**What it prevents**: Trying to restore a file that's already correct.

### 2. Post-Execution Check: File Exists in Correct Location

```python
# Verify file exists after checkout IN THE EXPECTED LOCATION
# Git checkout restores to git root, so check the actual git path
restored_path = os.path.join(git_toplevel, git_relative_path)
if not os.path.exists(restored_path):
    return RepairResult(
        success=False,
        error_message=f"File {git_relative_path} does not exist after git checkout"
    )
```

**What it prevents**: Claiming success when the file wasn't actually created.

### 3. Post-Execution Check: Changes Were Actually Made

```python
# Verify that something actually changed
# Check if the file now differs from the boiling branch
diff_result = subprocess.run(
    ["git", "diff", "--quiet", "boiling", "--", git_relative_path],
    cwd=git_toplevel,
    capture_output=True
)
if diff_result.returncode == 0:
    # No difference from boiling branch - restore didn't help
    return RepairResult(
        success=False,
        error_message=f"Restoring {file_path} did not create any changes"
    )
```

**What it prevents**: Claiming success when the restoration didn't change anything compared to the boiling branch.

## How It Works Now

### Before (Looping)

```
1. Detect ex.h is missing
2. git checkout ex.h → returns 0 (success)
3. File exists at some location
4. Report success=True
5. Next iteration: ex.h still missing (in wrong location)
6. Goto 1 → INFINITE LOOP
```

### After (Proper Validation)

```
1. Detect ex.h is missing
2. git checkout ex.h → returns 0 (success)
3. Check: Does file differ from boiling branch?
   → NO: File already existed there
4. Report success=False with error message
5. Pipeline tries next plan OR falls back to legacy handler
6. No infinite loop!
```

## Legacy System Comparison

The legacy `restore_missing_file` function had similar logic:

```python
deleted_files = get_deleted_files(ref=ref)

if relative_path in deleted_files:
    if git_checkout(relative_path, ref=ref):
        return True
else:
    print(f"{relative_path} is not deleted, looking for alternatives")
    # Try to find matching files...
```

It only returned `True` if:
1. The file was in the `deleted_files` set
2. `git_checkout` succeeded

Our new validation is even stricter:
- We check if changes were actually made
- We verify the file exists in the correct location
- We prevent restoring files that already match git

## Testing

Created `test_executor_validation.py`:

### Test 1: Validation Prevents Missing Files
```
✓ Validation correctly rejected: File nonexistent_file_xyz123.py not found in git
```

### Test 2: Executor Detects No-Change Restoration
```
✓ Executor correctly rejected: File test.py already matches git version at HEAD
```

## Impact

This fix prevents infinite loops in the pipeline by ensuring:

1. ✅ Only report success when changes were actually made
2. ✅ Detect when restoration doesn't help
3. ✅ Fall back to other plans or legacy handlers
4. ✅ Avoid wasting iterations on useless operations

## What Happens in Loop Scenario Now

**Old behavior**:
```
Iteration 7: ex.h → success=True (loop forever)
```

**New behavior**:
```
Iteration 7: ex.h → success=False "did not create any changes"
            → Try next plan
            → If all plans fail → Fall back to legacy handler
            → Legacy handler succeeds OR reports failure
```

The loop is broken because we properly detect when a restoration doesn't help.

## Files Modified

- `pipeline/executors/git_restore.py` - Added 3 validation checks
- `test_executor_validation.py` - Test suite
- `EXECUTOR_VALIDATION_FIX.md` - This document

## Related Issues

This is similar to the issue mentioned in the TODO in README.md:

> TODO: py_repair should fail if the restore results in no change.

We've implemented this for git restore. The same logic should be applied to other executors when they're created.

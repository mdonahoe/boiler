# Make Error Handler Migration

## Overview

Migrated `handle_make_missing_target` from the legacy handler system to the new 3-stage pipeline.

## Error Type

**Make missing target error:**
```
make: *** No rule to make target 'dim.c', needed by 'dim'.  Stop.
```

This occurs when:
- A Makefile references a source file that doesn't exist
- The file was deleted but the Makefile still expects it
- Make can't build an object file because the source is missing

## Migration Details

### 1. Created Detector

**File**: `pipeline/detectors/make_errors.py`

```python
class MakeMissingTargetDetector(Detector):
    """
    Detect make errors when a required source file is missing.

    Matches:
    - make: *** No rule to make target 'file.c', needed by 'target'.
    - make[1]: *** No rule to make target 'src/file.c', needed by 'target'.
    """
```

**Detection pattern:**
- Looks for `No rule to make target` in stderr
- Extracts the missing file name
- Extracts the target that needs it
- Captures subdirectory context if present

**Output:**
```json
{
  "clue_type": "make_missing_target",
  "confidence": 1.0,
  "context": {
    "file_path": "dim.c",
    "needed_by": "dim",
    "subdir": "/path/to/subdir"  // optional
  }
}
```

### 2. Created Planner

**File**: `pipeline/planners/make_restore.py`

```python
class MakeMissingTargetPlanner(Planner):
    """
    Plan fixes for make missing target errors.

    Strategy:
    1. If target is .o file, try to restore source (.c, .cc, .cpp)
    2. Consider subdirectory context if available
    3. Otherwise restore the missing file directly
    """
```

**Planning strategy:**

| Priority | Action | Example |
|----------|--------|---------|
| 0 | Restore source file for .o files | `dim.o` → restore `dim.c` |
| 1 | Restore file with subdirectory | `subdir/dim.c` |
| 2 | Restore file without subdirectory | `dim.c` |

**Generated plans:**
- For `dim.c` needed by `dim`: Creates plan to restore `dim.c`
- For `dim.o` needed by `dim`: Creates plans to restore `dim.c`, `dim.cc`, `dim.cpp`, etc.
- Handles subdirectory contexts automatically

### 3. Reused Executor

**Uses**: `GitRestoreExecutor` (already exists)

No new executor needed - the existing git restore executor handles all file restoration.

### 4. Registered Handlers

Updated `pipeline/handlers.py`:
```python
register_detector(MakeMissingTargetDetector())
register_planner(MakeMissingTargetPlanner())
```

## Testing

Created `test_make_error.py` to verify:
- ✅ Detects make missing target errors
- ✅ Extracts correct file name and context
- ✅ Generates repair plans with correct priority
- ✅ Plans include source file restoration for .o targets

### Test Output

```
Detected 1 error clue(s):
  1. ErrorClue(type=make_missing_target, context={'file_path': 'dim.c', 'needed_by': 'dim'})

Generated 1 repair plan(s):
  1. [Priority 2] restore_full on dim.c
     Reason: Restore dim.c (needed by dim)
```

## Real-World Verification

Tested with actual error from `/root/dim/.boil/`:

**Before** (legacy handler):
```json
{
  "success": false,
  "legacy_handler_used": "handle_make_missing_target"
}
```

**After** (new pipeline):
- Detector: ✅ Finds the error
- Planner: ✅ Creates restoration plan
- Executor: ✅ Would restore dim.c (validation works)

## Impact

This was the **#1 most-used legacy handler** in the dim repo test, so migrating it will have immediate impact.

## What's Handled

The new pipeline handler supports:

✅ Basic make errors: `make: *** No rule to make target 'file.c'`
✅ Subdirectory make errors: `make[1]: *** No rule to make target 'src/file.c'`
✅ Object file inference: `dim.o` → tries to restore `dim.c`, `dim.cc`, etc.
✅ Subdirectory context: Extracts and uses `Entering directory` info
✅ Multiple source extensions: Tries `.c`, `.cc`, `.cpp`, `.cxx`, `.C`

## Files Created/Modified

```
pipeline/detectors/make_errors.py        # NEW: Detector
pipeline/planners/make_restore.py        # NEW: Planner
pipeline/handlers.py                     # MODIFIED: Registration
test_make_error.py                       # NEW: Test
```

## Statistics

- **Lines added**: ~150
- **Components**: 1 detector, 1 planner
- **Handlers migrated**: 2 total (permission_denied, make_missing_target)
- **Handlers remaining**: 71

## Next Steps

Based on the analysis, the next highest-priority handlers to migrate are likely:
1. Python error handlers (NameError, ImportError)
2. Other build system errors (cargo, rust)
3. File system errors (cat, diff, shell commands)

Run `python3 analyze_boil_logs.py` after your next test run to see updated priorities.

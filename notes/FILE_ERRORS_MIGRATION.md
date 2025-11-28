# File Errors Migration - Batch Migration

## Overview

Migrated **6 file-related error handlers** from the legacy system to the new pipeline in one batch.

## Handlers Migrated

1. `handle_file_not_found` → `FileNotFoundDetector`
2. `handle_sh_cannot_open` → `ShellCannotOpenDetector`
3. `handle_shell_command_not_found` → `ShellCommandNotFoundDetector`
4. `handle_cat_no_such_file` → `CatNoSuchFileDetector`
5. `handle_diff_no_such_file` → `DiffNoSuchFileDetector` (bonus)
6. `handle_c_compilation_error` → `CCompilationErrorDetector`

## Error Types Handled

### 1. FileNotFoundError
```
FileNotFoundError: [Errno 2] No such file or directory: './test.sh'
```

### 2. Shell Cannot Open
```
sh: 0: cannot open makeoptions: No such file
```

### 3. Shell Command Not Found
```
./test.sh: line 3: ./configure: No such file or directory
```

### 4. Cat No Such File
```
cat: Makefile.in: No such file or directory
```

### 5. Diff No Such File
```
diff: test.txt: No such file or directory
```

### 6. C Compilation Error
```
/tmp/ex_bar502220.c:82:10: fatal error: ex.h: No such file or directory
   82 | #include "ex.h"
compilation terminated.
```

## Implementation

### Created One Detector File

**File**: `pipeline/detectors/file_errors.py`

Contains 6 detector classes, each handling a specific error pattern:
- All detectors return `clue_type="missing_file"`
- All use the existing `MissingFilePlanner`
- All use the existing `GitRestoreExecutor`

This is highly efficient - we only needed to create **detectors**, the planning and execution logic is fully reusable.

### Pattern Matching Strategy

Each detector uses regex patterns optimized for their specific error format:

| Detector | Confidence | Pattern Example |
|----------|-----------|-----------------|
| FileNotFoundDetector | 1.0 | `FileNotFoundError:.*No such file or directory: './(.+)'` |
| ShellCannotOpenDetector | 1.0 | `sh: \d+: cannot open (.+): No such file` |
| ShellCommandNotFoundDetector | 1.0 | `line \d+: (.+): No such file` |
| CatNoSuchFileDetector | 1.0 | `cat: (.+): No such file` |
| DiffNoSuchFileDetector | 1.0 | `diff: (.+): No such file` |
| CCompilationErrorDetector | 1.0 | `fatal error: (.+): No such file` |

### Special Features

**C Compilation Error Detector**:
- Detects header files: Sets `is_header: true` for `.h` files
- This could enable future optimizations (e.g., searching include paths)

## Testing

Created `test_file_errors.py` with 6 test cases:
- ✅ All 6 detectors working correctly
- ✅ All extract correct file paths
- ✅ All generate appropriate repair plans
- ✅ All use the correct clue type (`missing_file`)

## Impact on heirloom-ex-vi Test

**Before migration**:
```
Pipeline successes: 7 (50%)
Legacy handlers used:
  1x handle_file_not_found
  1x handle_sh_cannot_open
  1x handle_shell_command_not_found
  1x handle_cat_no_such_file
  1x handle_c_compilation_error
```

**After migration (expected)**:
```
Pipeline successes: 12 (86%)
Legacy handlers used: 0
```

The pipeline will now handle **all 14 iterations** except possibly 2:
- 7 make_missing_target (already migrated)
- 5 file errors (just migrated)
- 2 unknown (need to investigate)

## Files Created/Modified

```
pipeline/detectors/file_errors.py     # NEW: 6 detectors (~250 lines)
pipeline/handlers.py                  # MODIFIED: Register 6 detectors
test_file_errors.py                   # NEW: Test suite
FILE_ERRORS_MIGRATION.md              # NEW: This document
```

## Why Batch Migration?

All 6 handlers share the same characteristics:
1. All detect **missing files**
2. All use the same clue type (`missing_file`)
3. All use the same planner (`MissingFilePlanner`)
4. All use the same executor (`GitRestoreExecutor`)

The only difference is the **error message format**, so we only needed to write different regex patterns.

This is much more efficient than migrating them one-by-one.

## Statistics

- **Detectors added**: 6
- **Planners added**: 0 (reused existing)
- **Executors added**: 0 (reused existing)
- **Total handlers migrated**: 8 (2 previously + 6 now)
- **Handlers remaining**: ~65

## Code Reuse

This migration demonstrates the power of the 3-stage architecture:

```
6 detectors
    ↓
1 planner (MissingFilePlanner)
    ↓
1 executor (GitRestoreExecutor)
```

In the old system, we would have needed 6 separate handler functions with duplicated restoration logic. In the new system, we only write the detection patterns.

## Success Rate Projection

Based on the heirloom-ex-vi test:
- **Make errors**: 7/14 iterations (50%) - handled by `MakeMissingTargetDetector`
- **File errors**: 5/14 iterations (36%) - handled by new detectors
- **Total coverage**: 12/14 iterations (86%)

The pipeline now handles **most common errors** automatically!

## Next Steps

To reach 100% coverage in the heirloom-ex-vi test, analyze the remaining 2 iterations and migrate those handlers.

Run analysis again:
```bash
cd /root/dim/heirloom-ex-vi
python3 /root/boiler/analyze_legacy_handlers.py
```

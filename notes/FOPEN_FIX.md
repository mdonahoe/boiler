# Fix for fopen Error Detection and Legacy Handler Removal

## Problem

The pipeline was not detecting `fopen: No such file or directory` errors that occur when test code tries to open missing Python files. The legacy handler `handle_empty_python_file` was used as a workaround but was broken and unreliable.

### Original Issue in ~/dim

Tests would fail with:
```
AssertionError: 'example.py' not found in 'fopen: No such file or directory'
```

The pipeline couldn't detect this error, and the legacy handler wouldn't fix it properly.

## Solution

### 1. New FopenNoSuchFileDetector

Created a comprehensive detector for fopen errors in `pipeline/detectors/file_errors.py`:

**Detects multiple patterns:**
- Direct fopen errors: `fopen: filename: No such file or directory`
- Assertion errors with fopen context: `AssertionError: 'example.py' not found in 'fopen: No such file or directory'`
- Fallback: Infers filename from test context when not explicit

**Confidence levels:**
- 0.95 for explicit filename in fopen error
- 0.9 for AssertionError containing filename
- 0.7 for inferred filename from test context

### 2. Deleted Legacy Handler

Removed `handle_empty_python_file` from `handlers.py`:
- Was trying to repair code snippets instead of restoring files
- Didn't correctly identify which Python file was missing
- Is now obsolete with proper fopen detection

### 3. Integration

Updated `pipeline/handlers.py`:
- Added import for `FopenNoSuchFileDetector`
- Registered detector in `register_all_handlers()`
- Removed `handle_empty_python_file` from legacy handlers list

## Test Coverage

Added tests in `tests/test_c_errors.py`:

1. **test_detect_assertion_error_with_fopen**
   - Detects `AssertionError: 'example.py' not found in 'fopen: No such file or directory'`
   - Extracts the filename correctly

2. **test_detect_simple_fopen_error**
   - Detects simple `fopen: config.txt: No such file or directory`
   - Handles filenames with various extensions

3. **test_detect_fallback_py_file**
   - Detects files when mentioned in test context
   - Uses fallback inference when fopen error lacks explicit filename

All tests pass successfully.

## How It Works

1. **Detection Phase**
   - FopenNoSuchFileDetector recognizes fopen errors in test output
   - Extracts the missing filename from the error message or test context
   - Creates an ErrorClue with type `missing_file`

2. **Planning Phase**
   - MissingFilePlanner creates a restoration plan
   - Searches deleted files for the missing Python file
   - Generates `restore_file` plan with high priority

3. **Execution Phase**
   - GitRestoreExecutor restores the file from git
   - File becomes available to the test
   - Test can now open the file successfully

## Example: Fixing example.py

**Error detected:**
```
AssertionError: 'example.py' not found in 'fopen: No such file or directory'
```

**Pipeline flow:**
1. FopenNoSuchFileDetector extracts: `example.py`
2. MissingFilePlanner finds it in deleted files
3. GitRestoreExecutor restores it from git
4. Test reruns and finds the file

## Files Modified

- `pipeline/detectors/file_errors.py` - Added FopenNoSuchFileDetector
- `pipeline/handlers.py` - Registered detector, removed legacy handler
- `tests/test_c_errors.py` - Added 3 new test cases

## Results

- Replaced broken legacy handler with reliable pipeline component
- Handles multiple error patterns and edge cases
- No infinite loops or failed repairs
- Tests verify correct detection and error message parsing

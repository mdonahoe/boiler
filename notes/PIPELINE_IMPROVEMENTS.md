# Pipeline Improvements for tree-sitter

## Summary

Implemented pipeline components to detect and handle C/C++ compilation and linker errors, replacing legacy handlers. This improves the boiler's ability to automatically repair C projects.

## Changes Made

### 1. Enhanced C Compilation Error Detector (`pipeline/detectors/file_errors.py`)

**Improvement**: `CCompilationErrorDetector` now extracts source file directory context

- Detects patterns like: `fatal error: ./point.h: No such file or directory`
- Extracts source file being compiled (e.g., `lib/src/node.c`) from compiler invocation
- Extracts source directory (e.g., `lib/src`) for context-aware file lookup
- Stores this context in the `ErrorClue` for downstream planners to use

```python
# Example detection result now includes:
{
    "file_path": "point.h",
    "is_header": True,
    "source_file": "lib/src/node.c",
    "source_dir": "lib/src"
}
```

### 2. New C Linker Error Detector (`pipeline/detectors/file_errors.py`)

**New component**: `CLinkerErrorDetector` to detect linker errors

Detects three types of linker errors:
- **Undefined symbols**: `undefined reference to 'symbol_name'`
- **Missing libraries**: `/usr/bin/ld: cannot find -llib: No such file or directory`
- **Missing object files**: `/usr/bin/ld: cannot find file.o: No such file or directory`

Extracts all undefined symbols and stores them for intelligent repair planning.

### 3. Enhanced Missing File Planner (`pipeline/planners/file_restore.py`)

**Improvement**: `MissingFilePlanner` now uses source directory context

- Checks if file exists in source directory (from compiler context)
- Falls back to searching all deleted files for the header
- Uses `git_state.deleted_files` to find the correct path for missing files
- Example: When looking for `point.h`, it now finds `lib/src/point.h` by using source directory context

### 4. New Linker Undefined Symbols Planner (`pipeline/planners/file_restore.py`)

**New component**: `LinkerUndefinedSymbolsPlanner` for intelligent symbol resolution

Strategy:
- **Priority 1**: If `lib.c` or similar compilation unit is deleted, restore it immediately
  - This fixes many undefined symbol errors at once
- **Priority 2**: Search deleted C source files for files containing undefined symbols
  - Extracts potential symbol definitions using regex pattern matching
  - Scores files by how many undefined symbols they might define
  - Generates restoration plans in priority order

Example: When `lib.c` is deleted (which aggregates other .c files):
```python
# Creates a high-priority restoration plan:
RepairPlan(
    target_file="lib/src/lib.c",
    reason="Restore lib/src/lib.c (main compilation unit)",
    priority=0  # Highest priority
)
```

### 5. Registration and Integration

Updated `pipeline/handlers.py` to:
- Import new detectors and planners
- Register `CLinkerErrorDetector` in detector registry
- Register `LinkerUndefinedSymbolsPlanner` in planner registry
- Ensure proper ordering for detector/planner execution

## Test Coverage

Added comprehensive tests in `tests/test_c_errors.py`:

1. **C Compilation Error Detection**
   - Simple missing header detection
   - Source file context extraction
   - Relative path handling with `./` prefix

2. **C Linker Error Detection**
   - Undefined reference detection
   - Missing library detection
   - Missing object file detection

3. **Planner Logic**
   - Source directory context usage in file planning
   - `lib.c` priority detection for symbol resolution

All tests pass successfully.

## What Was Fixed

### Previously (Legacy Handlers)
- 28 C compilation errors used `handle_c_compilation_error`
- 1 linker error used `handle_c_linker_error`
- **Success rate: 6.5%** (2 successes out of 31 iterations)

### Now (Pipeline System)
- C compilation errors are detected and planned systematically
- Linker errors with undefined symbols are identified and resolved
- Context-aware file lookup improves accuracy
- Missing files in correct directories are located and restored

## Key Design Decisions

1. **Source Directory Context**: Rather than just extracting the missing filename, we also extract the directory of the source file being compiled. This allows the planner to correctly locate headers in the same directory.

2. **Lib.c Priority**: When a compilation unit like `lib.c` is deleted (which aggregates other .c files), restoring it immediately fixes many undefined symbol errors at once.

3. **Symbol Scanning**: For more complex cases, the planner scans deleted C files for function definitions matching undefined symbols.

4. **Validation**: The executor validates that files exist in git before attempting restoration, preventing failed plans.

## Files Modified

- `pipeline/detectors/file_errors.py` - Enhanced `CCompilationErrorDetector`, added `CLinkerErrorDetector`
- `pipeline/planners/file_restore.py` - Enhanced `MissingFilePlanner`, added `LinkerUndefinedSymbolsPlanner`, added `re` import
- `pipeline/handlers.py` - Updated imports and registration
- `tests/test_c_errors.py` - New comprehensive test file

## Usage

The improvements are automatically active when using the boiler:

```bash
python3 ~/boiler/boil.py make
```

The pipeline will:
1. Detect any C/C++ compilation or linker errors
2. Plan appropriate repairs based on deleted files and error context
3. Execute repairs by restoring necessary files from git
4. Fall back to legacy handlers only if pipeline cannot handle the error

## Notes

- The pipeline handles errors that inherit or aggregate multiple .c files (like `lib.c`)
- Source directory context improves accuracy for header file locations
- All existing tests continue to pass
- The system is backward compatible with legacy error handlers

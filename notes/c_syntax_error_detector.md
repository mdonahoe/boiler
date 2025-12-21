# C Syntax Error Detector and Planner

## Summary
Added support for detecting and fixing C syntax errors in header files caused by partial deletions or corruption.

## Components Added

### Detector: CSyntaxErrorDetector
- **File**: `pipeline/detectors/c_syntax_error.py`
- **Pattern**: Matches GCC errors like `expected identifier or '(' before 'void'`
- **Clue Type**: `c_syntax_error_in_header`
- **Example**:
  ```
  tree-sitter/lib/include/tree_sitter/api.h:1336:9: error: expected identifier or '(' before 'void'
  ```

### Planner: CSyntaxErrorPlanner
- **File**: `pipeline/planners/c_syntax_error.py`
- **Strategy**: Restore corrupted header files from git
- **Plan Type**: `restore_full`
- **Use Case**: When header files have syntax errors due to missing lines or corruption

### Executor
Uses existing `GitRestoreExecutor` to restore the entire file from git.

## Why This Was Added
In the dim repository, a one-line deletion in `tree-sitter/lib/include/tree_sitter/api.h` caused syntax errors throughout the build. The line `void ts_set_allocator(` was deleted, leaving an incomplete function declaration that triggered "expected identifier" errors.

The existing detectors couldn't handle this pattern because:
1. It's not a missing file (the header exists)
2. It's not a missing include (no includes are needed)
3. It's a syntax error from file corruption/partial deletion

## How It Works
1. **Detection**: Regex matches C syntax errors in `.h` files with patterns like "expected identifier...before 'X'"
2. **Planning**: Creates a plan to restore the entire header file from git HEAD
3. **Execution**: Uses `git checkout HEAD -- <file>` to restore the clean version

## Testing
- Tested successfully on `/root/dim` repo with one-line deletion
- Boiler detected 13 clues (one per compilation unit that included the broken header)
- Successfully restored the file and all tests passed
- Note: Not covered by example repo tests yet - would need to add corrupted header test case

## Future Improvements
- Could extend to detect other C syntax error patterns
- Could be smarter about detecting which specific line is corrupt (though full restore is safest)
- Should add test coverage in example repos (e.g., tree-sitter repo with corrupted api.h)

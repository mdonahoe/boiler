# Learnings from viw Repository Integration (2025-12-07)

## Summary
Successfully integrated boiler with the viw text editor repository, fixing multiple gaps in error detection and file restoration. The pipeline now handles 100% of errors without falling back to legacy handlers.

## Key Issues Discovered and Fixed

### 1. Missing Make Glob Pattern Error Detector
**Problem**: Make was reporting `make[2]: *** tests: No such file or directory. Stop.` when a directory referenced in the Makefile didn't exist, but boiler couldn't detect this error pattern.

**User Feedback Required**:
- User pointed out that boiler was "complaining about a missing header" initially (ncurses.h), which was a dependency issue, not a boiler problem.
- User then asked to "fix the new problem" after fixing the first issue, indicating the Make glob pattern error wasn't being handled.

**Solution**:
- Created `MakeGlobPatternErrorDetector` to detect pattern: `make[N]: *** <path>: No such file or directory. Stop.`
- This is distinct from `MakeMissingTargetDetector` which looks for "No rule to make target" errors.

### 2. Missing Directory Restoration
**Problem**: When Make referenced a directory like `tests/`, boiler detected it as a missing file but didn't know to restore all files within that directory.

**User Feedback Required**:
- User suggested: "can you make a missing directory planner instead maybe?"
- This was better than my initial approach of adding directory handling to MissingFilePlanner.

**Solution**:
- Created `MissingDirectoryPlanner` that:
  - Detects when a missing "file" is actually a directory (by checking if deleted files start with `path/`)
  - Detects glob patterns like `src/*.c` using fnmatch
  - Generates plans to restore all matching files
- Updated `MissingFilePlanner` to skip directories and glob patterns (delegates to MissingDirectoryPlanner)

**Key Learning**: Separation of concerns - better to have a specialized planner for directories/globs than to overload the MissingFilePlanner.

### 3. Legacy Handlers Masking Pipeline Gaps
**Problem**: Legacy handlers were automatically fixing errors that the pipeline couldn't handle, making it hard to know what was actually missing from the pipeline.

**User Feedback Required**:
- User asked: "why are you running make test manually? what feature is boil missing?"
- User then said: "actually, can you *disable* legacy handlers unless --legacy is passed to boil? then boil --abort and re-attempt"

**Solution**:
- Added `--legacy` flag to boil CLI
- Legacy handlers now only run when explicitly requested
- Changed default behavior to fail when pipeline can't handle an error (forces us to implement proper pipeline handlers)

**Key Learning**: Legacy fallbacks hide problems. By disabling them by default, we can see exactly what the pipeline is missing and fix it properly.

### 4. Test Failures Not Detected (C Tests)
**Problem**: When a C test failed due to a missing data file (`tests/file.txt`), boiler couldn't detect the test failure or determine what file was needed.

**User Feedback Required**:
- User explained: "that test failure is a legit boiler problem. the test requires 'file.txt' to exist so that the viw editor can read it."
- User specified: "I think boiler should be emitting a TestFailure detection for iter16.exit2.txt with the test_buffer.c as the filename of the test that failed."
- User explained the expected behavior: "A planner should be able to read the test file and see the filename 'file.txt' is in there and it should know that the file.txt needs to be restored"

**Solution**:
- Updated `TestFailureDetector` to detect C assertion failures with pattern: `<file>.c:<line>: <function>: Assertion \`<assertion>\` failed`
- Updated `TestFailurePlanner` to:
  - Search for test files in common test directories (`tests/`, `test/`, `t/`)
  - Extract file references from C code (string literals like `"./file.txt"`)
  - Extract file references from comments (e.g., `* ./tests/file.txt:`)
  - Handle both Python and C test files

**Key Learning**: Test failures are valuable error signals. By reading the test file, we can infer what data files are required and restore them automatically.

## Design Patterns Learned

### 1. Detector vs Planner Separation
- **Detectors**: Extract structured information from error messages (clues)
- **Planners**: Use clues + git state + file system to generate concrete repair plans
- Don't try to fix everything in the detector - keep it focused on pattern matching

### 2. Planner Priority and Delegation
- Use multiple specialized planners rather than one complex planner
- Have planners check if they should skip a clue and delegate to another planner
- Example: MissingFilePlanner skips glob patterns and delegates to MissingDirectoryPlanner

### 3. Test File Analysis
- Test files contain valuable hints about required dependencies
- Look for:
  - File paths in string literals
  - Files mentioned in comments (especially at top of C test files)
  - Command arguments
  - Assertion messages
- Search in common test directories when test file path is relative

### 4. Iterative Development with User Feedback
- Start with the most obvious error (missing ncurses.h dependency)
- Fix each error one at a time
- Let the user guide you when you're unsure (e.g., "make a missing directory planner")
- Use `--abort` and re-run to test from a clean state

## User Feedback That Improved the Solution

1. **"can you make a missing directory planner instead maybe?"**
   - Led to better separation of concerns
   - MissingDirectoryPlanner is now reusable for any directory/glob pattern

2. **"can you *disable* legacy handlers unless --legacy is passed"**
   - Forced proper pipeline implementation
   - Made it easy to see what was missing

3. **"use 'make check' instead of 'make test'"**
   - Faster validation during development
   - `make check` skips slow tests, `make test` runs everything

4. **"just add it to the todo/expected_components.json"**
   - When asked which test repo to update
   - User knows the codebase structure better

5. **Detailed explanation of test failure expectations**
   - User explained exactly what the detector should emit
   - User explained how the planner should work
   - This clear specification made implementation straightforward

## Metrics

- **Before**: Multiple legacy handlers needed, unclear what was missing
- **After**: 100% pipeline success rate, 0 legacy handlers used
- **Files restored**: 22 files across 16 iterations
- **Error types handled**: 5 (make_enter_directory, linker_undefined_symbols, missing_file, make_no_rule, test_failure)

## Testing Approach

1. Use `boil --abort` to reset to clean state
2. Run `boil make test` to see all iterations
3. Use `boil --check` to see pipeline statistics
4. Use `boil --handle-error <file>` to test specific error handling
5. Use `BOIL_VERBOSE=1` to see detailed planner/detector output
6. Always run `make check` in ~/boiler to ensure no regressions

## Files Modified

- `~/boiler/pipeline/detectors/make_errors.py` - Added MakeGlobPatternErrorDetector
- `~/boiler/pipeline/detectors/test_failures.py` - Added C test failure detection
- `~/boiler/pipeline/planners/file_restore.py` - Added MissingDirectoryPlanner, updated MissingFilePlanner
- `~/boiler/pipeline/planners/test_failures.py` - Enhanced test file analysis
- `~/boiler/pipeline/handlers.py` - Registered new detector and planner
- `~/boiler/boil.py` - Added --legacy flag, disabled legacy handlers by default
- `~/boiler/example_repos/tree-sitter/expected_components.json` - Updated detector usage
- `~/boiler/example_repos/todo/expected_components.json` - Added MissingDirectoryPlanner

## Remaining Observations

- The viw tests eventually fail with a legitimate assertion error (not a boiler problem)
- Some files remain deleted (LICENSE, README.md) but aren't needed for the build
- The pipeline correctly stops when there are no more errors to fix

## Future Improvements to Consider

- Could detect when tests are failing due to actual bugs (vs missing files) and suggest code fixes
- Could analyze test output to understand what data files should contain
- Could handle more complex glob patterns (e.g., `**/*.c`)
- Could cache test file analysis to avoid re-reading on every iteration

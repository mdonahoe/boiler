# Unwanted Content Removal Feature

**Date:** 2025-12-05
**Task:** Add support for detecting and removing unwanted content from files based on test failures

## Overview

Implemented a complete pipeline to detect test failures that check for unwanted content (e.g., "wasm" keyword in certain directories), and automatically remove matching lines from files.

## Use Case

The tree-sitter repository had a test that checked for unwanted "wasm" references in the public API headers (`lib/include/`). When files were restored from git, they contained wasm-related code that needed to be removed.

## Implementation

### 1. Detector (`pipeline/detectors/test_failures.py`)

**Pattern Added:**
```python
"git_grep_test_failure": r"Testing:\s+(?P<test_name>[^.]+)\.\.\.\s+FAIL\s+\((?P<keyword>\w+)\s+found\s+in\s+(?P<search_path>[^)]+)\)(?P<output_section>(?:\s*Found [^:]+:)?(?:\s*[^\n]+:\s*[^\n]+)*)"
```

**What it detects:**
- Test output like: `Testing: No wasm references in lib/include... FAIL (wasm found in lib/include/)`
- Captures: test name, keyword, search path, and the output section showing which files contain the keyword
- Uses RegexDetector base class (no method overrides)

**Example captured:**
```python
{
    "test_name": "No wasm references in lib/include",
    "keyword": "wasm",
    "search_path": "lib/include/",
    "output_section": "\n  Found wasm in:\nlib/include/tree_sitter/api.h:typedef struct wasm_engine_t TSWasmEngine;"
}
```

### 2. Planner (`pipeline/planners/test_failures.py`)

**Class:** `UnwantedContentPlanner`

**Strategy:**
1. Accepts `git_grep_test_failure` clue type
2. Parses the output section to extract file paths containing the keyword
3. Creates plans ONLY for header files (`.h`) to avoid breaking C source syntax
4. Skips `.c` files since removing arbitrary lines can create syntax errors

**Key Logic:**
```python
# Parse git grep output
file_pattern = rf"({re.escape(search_path)}[^\s:]+):.*?{re.escape(keyword)}"
for file_match in re.finditer(file_pattern, output_section, re.IGNORECASE):
    file_path = file_match.group(1)
    # Only plan for .h files
    if file_path.endswith('.h'):
        create_plan_to_remove_lines(file_path, keyword)
```

**Deduplication:**
- Uses `seen_targets` set with key `(file_path, keyword)` to avoid duplicate plans
- Fixed issue where both `git_grep_test_failure` and parsed `unwanted_content_in_files` were being processed

### 3. Executor (`pipeline/executors/file_edit.py`)

**Class:** `RemoveMatchingLinesExecutor`

**Function:**
- Removes all lines containing a specific keyword (case-insensitive)
- Validates file exists and is writable before execution
- Returns success even if no lines match (handles already-clean files)

**Key Features:**
```python
# Filter out lines containing keyword
if case_insensitive:
    pattern = re.compile(re.escape(keyword), re.IGNORECASE)
    filtered_lines = [line for line in lines if not pattern.search(line)]
else:
    filtered_lines = [line for line in lines if keyword not in line]

# Handle already-clean files gracefully
if original_content == new_content:
    print(f"No lines containing '{keyword}' found in {file_path} (already clean)")
    return RepairResult(success=True, ...)  # Success, not failure
```

### 4. Test Coverage (`tests/test_detector_examples.py`)

Added two new test methods:
- `test_all_patterns_have_examples()`: Ensures every PATTERN has a corresponding EXAMPLE
- `test_all_examples_match_patterns()`: Ensures every EXAMPLE corresponds to an actual PATTERN

**Example Added:**
```python
(
    "Testing: No wasm references in lib/include... FAIL (wasm found in lib/include/)\n  Found wasm in:\nlib/include/tree_sitter/api.h:typedef struct wasm_engine_t TSWasmEngine;",
    {
        "clue_type": "git_grep_test_failure",
        "confidence": 1.0,
        "context": {
            "test_name": "No wasm references in lib/include",
            "keyword": "wasm",
            "search_path": "lib/include/",
            "output_section": "\n  Found wasm in:\nlib/include/tree_sitter/api.h:...",
        },
    },
)
```

## Tree-Sitter Integration

### Test Added (`tree-sitter/test_tree_print.py`)

```python
# Test E4: Git grep for wasm in lib/include (should fail if found)
print(f"Testing: No wasm references in lib/include...", end=" ")
result = subprocess.run(
    ['git', 'grep', 'wasm', '--', 'lib/include/'],
    capture_output=True,
    text=True,
    cwd='/root/tree-sitter'
)
if result.returncode != 0:
    print("PASS (no wasm found)")
else:
    print("FAIL (wasm found in lib/include/)")
```

**Why lib/include/ not lib/:**
- Public API headers shouldn't expose internal implementation details
- Internal source files (lib/src/*.c) can have wasm implementation
- Removing lines from .c files breaks syntax (incomplete statements, dangling braces)
- Removing lines from .h files is safer (typically complete declarations)

## Results

**Successful Workflow:**
1. Iteration N: Restores missing `lib/include/tree_sitter/api.h` from git (contains wasm)
2. Iteration N+1: Test fails with "wasm found in lib/include/"
3. Detector captures: keyword="wasm", files=["lib/include/tree_sitter/api.h"]
4. Planner creates: remove_lines_matching plan for api.h
5. Executor removes: 35 lines containing "wasm"
6. Test passes: "No wasm references in lib/include... PASS"

**Performance:**
- Pipeline success rate: 96.9% (31/32 iterations)
- Error types handled: linker_undefined_symbols (692), missing_file (28), git_grep_test_failure (1)
- No legacy handlers needed - pipeline handled everything

## Key Fixes

### Issue 1: Duplicate Plans
**Problem:** Both `git_grep_test_failure` and parsed `unwanted_content_in_files` were being processed, creating duplicate plans.

**Solution:**
```python
# Only process unwanted_content_in_files after parsing
if clue.clue_type != "unwanted_content_in_files":
    continue
```

### Issue 2: Executor Failing on Clean Files
**Problem:** When retried, executor would fail if file was already clean, blocking pipeline.

**Solution:** Return success instead of failure when no lines match:
```python
if original_content == new_content:
    print(f"No lines containing '{keyword}' found (already clean)")
    return RepairResult(success=True, ...)
```

### Issue 3: Missing Pattern Coverage
**Problem:** No test to ensure all PATTERNS have EXAMPLES.

**Solution:** Added coverage tests that verify:
- Every pattern has at least one example
- Every example corresponds to an actual pattern
- Caught missing coverage in existing code (CImplicitDeclarationDetector)

## Files Modified

### New Files
- `pipeline/executors/file_edit.py` - RemoveMatchingLinesExecutor

### Modified Files
- `pipeline/detectors/test_failures.py` - Added git_grep_test_failure pattern, example
- `pipeline/planners/test_failures.py` - Added UnwantedContentPlanner, parsing logic
- `pipeline/handlers.py` - Registered new planner and executor
- `pipeline/detectors/base.py` - Added priority property to RegexDetector
- `tests/test_detector_examples.py` - Added pattern/example coverage tests
- `tree-sitter/test_tree_print.py` - Added wasm detection test

## Lessons Learned

1. **Keep detectors simple**: Use RegexDetector patterns instead of custom detect() methods
2. **Move complexity to planners**: Parsing and analysis logic belongs in planners, not detectors
3. **Be resilient in executors**: Handle edge cases (already fixed, file clean) gracefully
4. **Test coverage matters**: Automated checks for pattern/example coverage catch gaps early
5. **File type matters**: Removing lines from headers (.h) is safer than source files (.c)
6. **Deduplication is critical**: Same clue can be processed multiple times if not careful

## Testing

```bash
# Run boiler tests
cd /root/boiler && make check
# Result: 65/66 tests pass (1 pre-existing failure)

# Test tree-sitter integration
cd /root/tree-sitter
make clean
/root/boiler/boil ./test_tree_print.py
# Result: Wasm test passes, wasm removed from api.h

# Verify wasm removal
git grep wasm -- lib/include/
# Result: No matches (exit code 1)
```

## Future Improvements

1. **Smarter line removal**: Use AST parsing for C files to remove complete code blocks
2. **Configurable patterns**: Allow tests to specify what content is unwanted
3. **Multi-file coordination**: Handle cases where removing from one file requires changes in others
4. **Semantic analysis**: Understand code structure to avoid breaking syntax

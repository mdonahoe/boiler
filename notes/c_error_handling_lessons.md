# C Error Handling Improvements - Lessons Learned

## Problem Statement
Boiler was incorrectly handling C compilation/linker errors and claiming successful repairs without actually modifying files, causing infinite loops in the repair process.

## Key Learnings

### 1. File Validation is Essential
**Lesson**: Never trust that a repair tool successfully modified a file without verifying the change.

**Implementation**: 
- Capture file hash before repair attempt
- Verify hash changes after repair
- Return failure if no changes detected
- This prevents false "success" claims that cause infinite loops

**Why this matters**: 
- src_repair uses git history to restore code, but only if that code actually exists in git
- If a symbol doesn't exist in git history (e.g., stdlib functions), src_repair silently succeeds without modifying the file
- Without validation, boil would claim success and loop indefinitely

### 2. Distinguish Between Error Types
**Lesson**: Not all undeclared symbols are project functions that need restoration.

**Three categories**:
1. **Missing includes/headers** - stdlib functions (`open`, `printf`, `va_start`) and constants (`O_RDWR`, `SIGTERM`)
   - Need `#include <header.h>` additions
   - NOT restorable via git history (src_repair won't find them)
   - Should skip creating repair clues

2. **Missing project functions** - custom functions defined elsewhere in the project
   - Exist in git history but may be deleted or need forward declarations
   - Restorable via src_repair with `--missing` flag
   - Should create repair clues

3. **Declaration/ordering issues** - functions defined later than first use
   - May already exist in file but in wrong order
   - Need forward declarations
   - src_repair can handle these

**Implementation**:
- Maintain lists of known stdlib functions and constants
- Filter these out before creating repair clues
- Only attempt restoration for project-specific symbols

### 3. Dynamic > Hardcoded
**Lesson**: Never hardcode repo-specific filenames or paths.

**Example of what NOT to do**:
```python
# BAD: Repo-specific
if f in ('dim.c', 'main.c'):
    priority_files.append(f)
```

**Better approach**:
```python
# GOOD: Dynamic based on git state
if git_relative in modified_set:  # Files being actively worked on
    score += 10
if git_relative in deleted_set:   # Files with history
    score += 5
if '/' not in f:                  # Root directory
    score += 1
```

**Why**: 
- Boiler is a generic repair tool
- Must work across any C project
- Git state tells us what's actively being changed
- Modified files are most likely compilation targets

### 4. Compiler Hint Matching Complexity
**Lesson**: GCC uses Unicode smart quotes, not ASCII quotes.

**Problem**: Error messages contain fancy Unicode quotes (') not ASCII (')
```
dim.c:159:10: error: 'disableRawMode' undeclared
                      ^ Unicode left quote
```

**Solution**: Match both ASCII and Unicode quote characters in regex:
```python
['\u2018]([^'\u2019]+)['\u2019]  # Unicode quotes U+2018, U+2019
# AND/OR
['']([^'']+)['']  # ASCII single quotes
```

### 5. Error Detector Matching Order Matters
**Lesson**: Some errors have multiple interpretations depending on context.

**Example - Implicit declarations without include suggestions**:
- Could be stdlib function (needs include)
- Could be project function (needs restoration)
- Could be forward declaration issue (needs reordering)

**Solution**: Check compiler hints for include suggestions first
1. Does error have "include '<header.h>'" suggestion? → missing_c_include
2. Is it a known stdlib function/constant? → skip (can't fix)
3. Otherwise? → missing_c_function (likely project code)

## Recommendations for Future Improvements

### 1. Implement Proper Include Header Support
Currently, the pipeline doesn't add missing includes. This would require:
- Maintaining a comprehensive stdlib function→header mapping
- Creating an executor to add include directives
- Testing with various C standards (C89, C99, C11)

### 2. Improve Constant/Macro Detection
The current stdlib_constants list is basic. Better approach:
- Use compiler's error messages that suggest headers
- Parse error output for "is defined in header" notes
- Extract header name automatically

### 3. Add Forward Declaration Support
When src_repair fails for ordering issues:
- Detect if function is defined later in file
- Generate appropriate forward declaration
- Insert at top of file

### 4. Handle Multiple Error Types Per Iteration
Currently we process errors sequentially. Could:
- Group related errors (all missing stdlib.h includes together)
- Fix multiple issues in one pass
- Reduce iteration count

## Testing Notes
- Test with various C standards and compiler versions
- GCC uses Unicode quotes; clang may differ
- Some stdlib functions appear in multiple headers (e.g., `exit` in both stdlib.h and unistd.h)
- Different systems may have different stdlib paths/availability

## Files Modified
1. `pipeline/detectors/file_errors.py` - CImplicitDeclarationDetector, CUndeclaredIdentifierDetector
2. `pipeline/executors/c_code_restore.py` - Added file change validation
3. `pipeline/planners/file_restore.py` - Dynamic file prioritization

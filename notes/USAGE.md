# identify_removable.py - Usage Guide

## Overview

Tool to identify and remove unused/dead code from C/Python projects using AST analysis and empirical testing.

## Features

1. **Static Analysis**: Analyze function usage and identify removal candidates
2. **Safe Removal**: Remove functions with verification that references are also removed
3. **Empirical Testing**: Test removals against your test suite to ensure safety

---

## Modes of Operation

### 1. List Candidates (Analysis Only)

Lists functions ranked by removability score without making any changes.

```bash
# Show all candidates
python3 identify_removable.py file.c

# Limit to top 5
python3 identify_removable.py file.c --limit 5

# Analyze multiple files
python3 identify_removable.py src/*.c --limit 10
```

**Output:**
```
======================================================================
REMOVABLE FUNCTION CANDIDATES
======================================================================

1. deadFunction
   Score: 1000
   Reason: Dead code (declared but never called)
   Declared in: 1 file(s)
     - file.c

2. rarelyUsed
   Score: 400
   Reason: Minimally used (1 call)
   Declared in: 1 file(s)
     - file.c
   Called in: 1 location(s)
     - file.c
```

---

### 2. Manual Removal

Remove a specific function by name.

```bash
# Dry run (show what would change)
python3 identify_removable.py file.c --remove myFunction

# Actually modify the file
python3 identify_removable.py file.c --remove myFunction --inplace
```

**Features:**
- ✅ Removes function definition
- ✅ Removes all references (calls, declarations, callback parameters)
- ✅ Verifies complete removal (fails if references remain)
- ✅ Safe: Won't modify file if removal verification fails

---

### 3. Auto-Remove Top Candidate

Automatically removes the highest-scored (most removable) function.

```bash
python3 identify_removable.py file.c --auto --inpl
```

**Use case:** Iteratively remove dead code in a loop.

---

### 4. Empirical Testing Mode ⭐ NEW

**The safest approach**: Test each removal against your test suite before committing.

```bash
# Test top 10 candidates
python3 identify_removable.py file.c --test-removal

# Test top 20 with custom test command
python3 identify_removable.py file.c --test-removal --num-tests 20 --test-command "npm test"

# For projects without Makefiles
python3 identify_removable.py file.c --test-removal --test-command "gcc file.c && ./a.out"
```

**How it works:**
1. For each candidate function:
   - Creates backup of file
   - Removes the function
   - Runs your test command
   - Records: ✅ pass / ⚠️ fail / ❌ couldn't remove
   - Restores file from backup
2. Prints comprehensive report

**Output:**
```
======================================================================
EMPIRICAL REMOVAL TEST - Testing top 3 candidates
Test command: make test
======================================================================

[1/3] Testing removal of 'unused'...
  Score: 1000 - Dead code (declared but never called)
  Declared in: file.c
  ✅ Tests PASSED - Safe to remove!

[2/3] Testing removal of 'criticalFunction'...
  Score: 1000 - Dead code (declared but never called)
  Declared in: file.c
  ⚠️  Tests FAILED - Removal would break tests

[3/3] Testing removal of 'callbackFunc'...
  Score: 400 - Minimally used (1 call)
  Declared in: file.c
  ❌ Removal failed: Removal verification failed


======================================================================
EMPIRICAL TEST REPORT
======================================================================

Summary:
  Total tested: 3
  ✅ Safe to remove (tests pass): 1
  ⚠️  Breaks tests: 1
  ❌ Failed removal: 1

Functions that can be safely removed:
  ✅ unused (score: 1000) - Dead code (declared but never called)
```

---

## All Options

```
positional arguments:
  files                 Source files to analyze

options:
  -h, --help            show this help message and exit
  --limit LIMIT         Limit number of candidates to show
  --include-external    Include external/library functions in analysis
  --remove FUNCTION_NAME
                        Remove the specified function from its source file(s)
  --inplace             Modify files in-place when using --remove
  --auto-remove-top     Automatically remove the top candidate
  --test-removal        Empirically test removal of top candidates by running tests
  --num-tests NUM_TESTS
                        Number of functions to test empirically (default: 10)
  --test-command TEST_COMMAND
                        Command to run for testing (default: "make test")
```

---

## Workflow Examples

### Safe Cleanup Workflow

1. **Identify candidates:**
   ```bash
   python3 identify_removable.py src/*.c --limit 20
   ```

2. **Test removals empirically:**
   ```bash
   python3 identify_removable.py src/*.c --test-removal --num-tests 10
   ```

3. **Remove safe functions:**
   ```bash
   # Based on the report, manually remove confirmed-safe functions
   python3 identify_removable.py src/file.c --remove safeFunction --inplace
   ```

4. **Verify with tests:**
   ```bash
   make test
   git commit -am "Remove unused function: safeFunction"
   ```

### Aggressive Cleanup (with git safety net)

```bash
# Make sure you have a clean git state first!
git status

# Auto-remove top candidate in a loop
for i in {1..5}; do
    python3 identify_removable.py file.c --auto --inpl && make test || git checkout file.c
done
```

---

## Understanding Removability Scores

- **1000**: Dead code (declared but never called) - **highest priority**
- **400-500**: Minimally used (1-2 calls)
- **200-300**: Low usage (3-5 calls)
- **<200**: Moderate/high usage

---

## Safety Features

✅ **Backup & Restore**: Empirical testing always restores files
✅ **Verification**: Confirms no references remain after removal
✅ **Non-destructive**: Analysis modes never modify files
✅ **Clear Feedback**: Detailed error messages when removal fails

---

## Requirements

- Python 3.6+
- `tree_print` command (for AST parsing)
- Tree-sitter grammars for your language

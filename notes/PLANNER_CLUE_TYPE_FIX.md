# Planner Clue Type Handling Fix

**Date:** 2025-11-30
**Issue:** New clue types created during detector refactoring were not being handled by planners

## Problem

When adding back deleted detector patterns, I created new clue types:
- `missing_file_assertion` (from FopenNoSuchFileDetector)
- `missing_file_simple` (from FileNotFoundDetector)
- `missing_file_not_found` (from ShellCommandNotFoundDetector)

The base `RegexDetector` class uses **pattern name as clue_type** (line 120 in base.py):
```python
clue_type=pattern_name
```

This meant `MissingFilePlanner` which only handled `clue_type == "missing_file"` would ignore these new variations.

## Solution

Changed `MissingFilePlanner.can_handle()` from exact match to prefix match:

```python
# Before
def can_handle(self, clue_type: str) -> bool:
    return clue_type == "missing_file"

# After
def can_handle(self, clue_type: str) -> bool:
    return clue_type.startswith("missing_file")
```

## Why This Works

All missing file clue types now start with `"missing_file"`:
- `missing_file` ✅
- `missing_file_assertion` ✅
- `missing_file_simple` ✅
- `missing_file_not_found` ✅

The planner can handle all variations with one check.

## Alternative Considered

**Using PATTERNS as a list** (suggested by user):
```python
PATTERNS = [
    ("missing_file", r"pattern1"),
    ("missing_file", r"pattern2"),  # Same name, different pattern
]
```

This would allow multiple patterns with the same clue_type, avoiding the need for unique names like `missing_file_assertion`. However, this would require changing the base class to iterate over a list instead of a dict.

## Current Status

- ✅ All 49 tests passing
- ✅ New patterns properly detected
- ✅ Planner correctly handles all `missing_file*` clue types
- ✅ No architecture violations (no method overrides)

## Pattern Naming Convention

When creating multiple patterns that should be handled by the same planner:
- Use a **common prefix** (e.g., `missing_file_*`)
- Make planner use `startswith()` check
- Or use exact names and handle each explicitly in `can_handle()`

## Files Modified

- `pipeline/planners/file_restore.py` - Updated `MissingFilePlanner.can_handle()`
- `pipeline/detectors/file_errors.py` - Added patterns with descriptive suffixes

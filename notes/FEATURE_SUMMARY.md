# Feature Summary: Legacy Handler Tracking

## What Was Added

The JSON debug output now tracks **which legacy handler was used** when the pipeline fails to find a fix.

## Changes Made

### 1. Modified `boil.py`

- Added `legacy_handler_used` variable to track handler name
- Captures `handler.__name__` when legacy handler succeeds
- Prints `[Legacy] Used legacy handler: {name}` to console
- Adds `legacy_handler_used` field to JSON debug output

### 2. Created Analysis Tool

- `analyze_boil_logs.py` - Analyzes all pipeline JSON files
- Shows which legacy handlers are used most frequently
- Provides migration priority recommendations
- Displays pipeline success rate

### 3. Added Documentation

- `LEGACY_HANDLER_TRACKING.md` - Complete feature documentation
- `FEATURE_SUMMARY.md` - This file

## Example JSON Output

### When Pipeline Succeeds

```json
{
  "success": true,
  "files_modified": ["./test.py"],
  "clues_detected": [...],
  "plans_generated": [...],
  "plans_attempted": [...],
  "legacy_handler_used": null
}
```

### When Legacy Handler Is Used

```json
{
  "success": false,
  "files_modified": [],
  "error_message": "No error clues detected by any detector",
  "clues_detected": [],
  "plans_generated": [],
  "plans_attempted": [],
  "legacy_handler_used": "handle_name_error"
}
```

## Console Output

When running `boil.py`, you'll now see:

```
[Pipeline] Attempting repair with new pipeline system...
[Pipeline] Pipeline did not produce a fix, falling back to old handlers...
[Legacy] Used legacy handler: handle_name_error
[Pipeline] Debug info saved to .boil/iter1.pipeline.json
```

## Usage

### Analyze Legacy Handler Usage

```bash
python3 analyze_boil_logs.py
```

Output shows:
- Pipeline success rate
- Error types detected by pipeline
- Most frequently used legacy handlers
- Migration priority recommendations

### Example Analysis Output

```
================================================================================
LEGACY HANDLERS USED (Most Common First)
================================================================================
    8x  handle_name_error
    3x  handle_import_error1
    2x  handle_missing_file
    1x  handle_module_attribute_error

================================================================================
MIGRATION PRIORITY RECOMMENDATIONS
================================================================================
Migrate these handlers next (highest impact first):

  1. handle_name_error
     Used 8 time(s)

  2. handle_import_error1
     Used 3 time(s)
```

## Benefits

1. **Data-driven migration** - Know exactly which handlers to migrate
2. **Track progress** - See success rate improve over time
3. **Identify patterns** - Group similar handlers for batch migration
4. **Measure impact** - Quantify the benefit of each migration

## Testing

Created `test_legacy_tracking.py` to verify:
- ✓ Legacy handler name is captured correctly
- ✓ JSON includes `legacy_handler_used` field
- ✓ Field is `null` when pipeline succeeds
- ✓ Field contains handler name when pipeline fails

## Complete Feature List

The pipeline now provides:

1. ✅ **3-stage architecture** (Detect → Plan → Execute)
2. ✅ **JSON debug output** (`.boil/iterN.pipeline.json`)
3. ✅ **Legacy handler tracking** (which old handler was used)
4. ✅ **Analysis tool** (prioritize migrations)
5. ✅ **Fallback mechanism** (old handlers as safety net)

## Next Steps

1. Run your test suite through `boil.py`
2. Run `python3 analyze_boil_logs.py`
3. Migrate the top 3-5 most-used legacy handlers
4. Re-run analysis to see improvement

This creates a **data-driven migration process** where you can measure progress and prioritize high-impact work.

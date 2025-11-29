# Legacy Handler Tracking

## Overview

When the pipeline fails to find a fix and falls back to the old handler system, we now track **which legacy handler was used** in the JSON debug output.

This helps you prioritize which handlers to migrate next.

## JSON Output

Each `.boil/iterN.pipeline.json` now includes:

```json
{
  "success": false,
  "files_modified": [],
  "error_message": "No error clues detected by any detector",
  "clues_detected": [],
  "plans_generated": [],
  "plans_attempted": [],
  "legacy_handler_used": "handle_name_error"  // <-- NEW FIELD
}
```

## Values

- `null` - Pipeline successfully handled the error
- `"handle_name_error"` - Pipeline failed, legacy handler `handle_name_error` was used
- `"handle_import_error1"` - Pipeline failed, legacy handler `handle_import_error1` was used
- etc.

## Console Output

When a legacy handler is used, you'll see:

```
[Pipeline] Pipeline did not produce a fix, falling back to old handlers...
[Legacy] Used legacy handler: handle_name_error
```

## Analysis Tool

Use `analyze_boil_logs.py` to see which handlers are used most frequently:

```bash
python3 analyze_boil_logs.py
```

### Example Output

```
================================================================================
PIPELINE PERFORMANCE
================================================================================
Pipeline successes: 5
Pipeline failures:  15
Success rate:       25.0%

================================================================================
ERROR TYPES DETECTED BY PIPELINE
================================================================================
  permission_denied              :   5 times

================================================================================
LEGACY HANDLERS USED (Most Common First)
================================================================================
    8x  handle_name_error
    3x  handle_import_error1
    2x  handle_missing_file
    1x  handle_module_attribute_error
    1x  handle_rust_module_not_found

================================================================================
MIGRATION PRIORITY RECOMMENDATIONS
================================================================================
Migrate these handlers next (highest impact first):

  1. handle_name_error
     Used 8 time(s)
     Examples: iter2.pipeline.json, iter4.pipeline.json, iter7.pipeline.json

  2. handle_import_error1
     Used 3 time(s)
     Examples: iter3.pipeline.json, iter9.pipeline.json, iter12.pipeline.json

  3. handle_missing_file
     Used 2 time(s)
     Examples: iter5.pipeline.json, iter10.pipeline.json
```

## Migration Priority

Based on the analysis, migrate handlers in this order:

1. **Highest usage** - Handlers used most frequently
2. **Related handlers** - Group similar handlers together (e.g., all Python import handlers)
3. **Shared infrastructure** - Handlers that can reuse existing planners/executors

## Benefits

1. **Data-driven prioritization** - Know exactly which handlers to migrate next
2. **Track progress** - See success rate improve as you migrate handlers
3. **Identify patterns** - Group similar errors together
4. **Measure impact** - See how much each migration helps

## Example Workflow

1. Run your test suite through `boil.py`
2. Analyze the results: `python3 analyze_boil_logs.py`
3. Migrate the top 3 legacy handlers
4. Run the test suite again
5. See improved success rate!

## Files Modified

- `boil.py` - Tracks which legacy handler was used
- `boil.py` - Saves `legacy_handler_used` to JSON
- `boil.py` - Prints `[Legacy] Used legacy handler: ...` message

## Implementation Details

```python
# In boil.py
legacy_handler_used = None

# Try pipeline first
pipeline_result = run_pipeline(...)

# Fall back to legacy handlers
if not message:
    for handler in handlers.HANDLERS:
        if handler(err) and has_changes():
            legacy_handler_used = handler.__name__  # <-- Capture name
            message = f"fixed with {handler}"
            print(f"[Legacy] Used legacy handler: {legacy_handler_used}")
            break

# Save to JSON
debug_data = pipeline_result.to_dict()
debug_data["legacy_handler_used"] = legacy_handler_used  # <-- Add to JSON
```

## Next Steps

After running your test suite through `boil.py`:

1. Run `python3 analyze_boil_logs.py`
2. Identify the top 5 most-used legacy handlers
3. Check which ones are similar (e.g., all Python errors)
4. Migrate them together as a group
5. Re-run analysis to track progress

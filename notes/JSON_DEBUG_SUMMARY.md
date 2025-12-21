# JSON Debug Feature - Implementation Summary

## What Was Added

The pipeline now saves detailed debug information to **`.boil/iterN.pipeline.json`** for each iteration.

## Files Modified

1. **`pipeline/models.py`**
   - Added `clues_detected` and `plans_generated` fields to `RepairResult`
   - Added `to_dict()` method for JSON serialization

2. **`pipeline/pipeline.py`**
   - Updated to populate debug fields in `RepairResult`
   - All return paths now include clues and plans

3. **`boil.py`**
   - Added `import json`
   - Saves `iterN.pipeline.json` after each pipeline run
   - Logs JSON save location

## JSON Format

Each `.boil/iterN.pipeline.json` contains:

```json
{
  "success": boolean,
  "files_modified": [array of file paths],
  "error_message": string or null,
  "clues_detected": [
    {
      "clue_type": string,
      "confidence": float,
      "context": {dictionary},
      "source_line": string
    }
  ],
  "plans_generated": [
    {
      "plan_type": string,
      "priority": int,
      "target_file": string,
      "action": string,
      "params": {dictionary},
      "reason": string
    }
  ],
  "plans_attempted": [
    {same structure as plans_generated}
  ]
}
```

## Testing

Created `test_json_debug.py` which verifies:
- ✓ JSON is created successfully
- ✓ JSON is valid and parseable
- ✓ All expected fields are present
- ✓ Clues are captured correctly
- ✓ Plans are captured correctly

## Example Output

From `.boil/test_debug.json`:

```json
{
  "success": true,
  "files_modified": ["./test.py"],
  "error_message": null,
  "clues_detected": [
    {
      "clue_type": "permission_denied",
      "confidence": 1.0,
      "context": {"file_path": "./test.py"},
      "source_line": "Permission denied: './test.py'"
    }
  ],
  "plans_generated": [
    {
      "plan_type": "restore_permissions",
      "priority": 1,
      "target_file": "./test.py",
      "action": "restore_full",
      "params": {"ref": "HEAD"},
      "reason": "File ./test.py has wrong permissions, restoring from git"
    }
  ],
  "plans_attempted": [
    {
      "plan_type": "restore_permissions",
      "priority": 1,
      "target_file": "./test.py",
      "action": "restore_full",
      "reason": "File ./test.py has wrong permissions, restoring from git"
    }
  ]
}
```

## Benefits

1. **Full Visibility**: See exactly what the pipeline detected, planned, and executed
2. **Debugging**: Understand why a fix succeeded or failed
3. **Analysis**: Can be parsed programmatically for metrics
4. **Reproducibility**: Can replay the exact clues/plans if needed
5. **Testing**: Validate detector/planner/executor behavior

## Backward Compatibility

- Old text files (`.boil/iterN.exit{code}.txt`) are still created
- JSON files are **additive** - they don't replace anything
- If JSON save fails, a warning is printed but execution continues

## Usage During Boiling

When you run `boil.py`, you'll now see:

```
Attempt 1
[Pipeline] Attempting repair with new pipeline system...
[Pipeline] Debug info saved to .boil/iter1.pipeline.json
[Pipeline] Success: fixed with pipeline (modified 1 file(s))
```

Then you can inspect:

```bash
# View the debug info
cat .boil/iter1.pipeline.json | jq .

# See what was detected
cat .boil/iter1.pipeline.json | jq '.clues_detected'

# See what plans were generated
cat .boil/iter1.pipeline.json | jq '.plans_generated'

# Check if it succeeded
cat .boil/iter1.pipeline.json | jq '.success'
```

## Error Handling

If JSON serialization fails:
- A warning is printed: `[Pipeline] Warning: Could not save debug JSON: {error}`
- Boiling continues normally
- The iteration is not lost - the text file still exists

## Documentation

Created comprehensive documentation:
- **DEBUG_JSON_EXAMPLE.md**: Shows various JSON examples and usage patterns
- **This file**: Implementation summary

## Next Steps

The JSON debug feature is **complete and working**. Future enhancements could include:

1. Timing information (how long each stage took)
2. Git state snapshot at each iteration
3. Executor detailed logs
4. Aggregated metrics across all iterations

But the core feature is done and tested ✓

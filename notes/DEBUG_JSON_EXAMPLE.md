# Debug JSON Output

The pipeline now saves detailed debug information to `.boil/iterN.pipeline.json` for each iteration.

## Location

- **Pattern**: `.boil/iter{N}.pipeline.json`
- **Example**: `.boil/iter1.pipeline.json`, `.boil/iter2.pipeline.json`, etc.

## Structure

Each JSON file contains:

```json
{
  "success": true/false,
  "files_modified": ["list", "of", "files"],
  "error_message": "error string or null",
  "clues_detected": [...],
  "plans_generated": [...],
  "plans_attempted": [...]
}
```

## Example: Successful Permission Fix

```json
{
  "success": true,
  "files_modified": [
    "./test.py"
  ],
  "error_message": null,
  "clues_detected": [
    {
      "clue_type": "permission_denied",
      "confidence": 1.0,
      "context": {
        "file_path": "./test.py"
      },
      "source_line": "Permission denied: './test.py'"
    }
  ],
  "plans_generated": [
    {
      "plan_type": "restore_permissions",
      "priority": 1,
      "target_file": "./test.py",
      "action": "restore_full",
      "params": {
        "ref": "HEAD"
      },
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

## Example: No Error Detected

```json
{
  "success": false,
  "files_modified": [],
  "error_message": "No error clues detected by any detector",
  "clues_detected": [],
  "plans_generated": [],
  "plans_attempted": []
}
```

## Example: Multiple Clues with Prioritization

```json
{
  "success": true,
  "files_modified": [
    "src/helper.py"
  ],
  "error_message": null,
  "clues_detected": [
    {
      "clue_type": "missing_file",
      "confidence": 1.0,
      "context": {
        "file_path": "src/helper.py"
      },
      "source_line": "FileNotFoundError: src/helper.py"
    },
    {
      "clue_type": "permission_denied",
      "confidence": 0.8,
      "context": {
        "file_path": "src/main.py"
      },
      "source_line": "Permission denied: src/main.py"
    }
  ],
  "plans_generated": [
    {
      "plan_type": "restore_file",
      "priority": 0,
      "target_file": "src/helper.py",
      "action": "restore_full",
      "params": {
        "ref": "HEAD"
      },
      "reason": "File src/helper.py is missing"
    },
    {
      "plan_type": "restore_permissions",
      "priority": 1,
      "target_file": "src/main.py",
      "action": "restore_full",
      "params": {
        "ref": "HEAD"
      },
      "reason": "File src/main.py has wrong permissions"
    }
  ],
  "plans_attempted": [
    {
      "plan_type": "restore_file",
      "priority": 0,
      "target_file": "src/helper.py",
      "action": "restore_full",
      "reason": "File src/helper.py is missing"
    }
  ]
}
```

Note: In this example, only the first plan (priority 0) was attempted because it succeeded. The second plan (priority 1) was never executed.

## Example: Failed Validation

```json
{
  "success": false,
  "files_modified": [],
  "error_message": "All repair plans failed",
  "clues_detected": [
    {
      "clue_type": "permission_denied",
      "confidence": 1.0,
      "context": {
        "file_path": "./nonexistent.py"
      },
      "source_line": "Permission denied: './nonexistent.py'"
    }
  ],
  "plans_generated": [
    {
      "plan_type": "restore_file",
      "priority": 0,
      "target_file": "./nonexistent.py",
      "action": "restore_full",
      "params": {
        "ref": "HEAD"
      },
      "reason": "File ./nonexistent.py is missing"
    }
  ],
  "plans_attempted": []
}
```

Note: No plans were attempted because validation failed (file doesn't exist in git).

## Using Debug JSON

### View in Terminal

```bash
# Pretty print the latest iteration
cat .boil/iter*.pipeline.json | jq .

# View just the clues detected
cat .boil/iter1.pipeline.json | jq '.clues_detected'

# View just the plans generated
cat .boil/iter1.pipeline.json | jq '.plans_generated'

# See which files were modified
cat .boil/iter*.pipeline.json | jq '.files_modified'
```

### Analyze Failures

```bash
# Find all failed iterations
for f in .boil/iter*.pipeline.json; do
  if jq -e '.success == false' "$f" >/dev/null; then
    echo "Failed: $f"
    jq '.error_message' "$f"
  fi
done
```

### Track Progress

```bash
# Count clues detected per iteration
for f in .boil/iter*.pipeline.json; do
  count=$(jq '.clues_detected | length' "$f")
  echo "$f: $count clue(s)"
done
```

## Comparison: Old vs New

### Old System
```
.boil/iter1.exit127.txt
.boil/iter2.exit127.txt
.boil/iter3.exit0.txt
```

You only get the stderr/stdout text. No structured information about what was detected or why.

### New System
```
.boil/iter1.exit127.txt       # Still have the raw output
.boil/iter1.pipeline.json     # NEW: Structured debug info
.boil/iter2.exit127.txt
.boil/iter2.pipeline.json     # NEW: Shows what changed
.boil/iter3.exit0.txt
.boil/iter3.pipeline.json     # NEW: Shows final success state
```

Now you have both:
1. Raw stderr/stdout (for manual inspection)
2. Structured JSON (for automated analysis)

## Benefits

1. **Reproducibility**: Re-run with exact same clues/plans
2. **Analysis**: Understand why something succeeded or failed
3. **Debugging**: See exactly what the pipeline detected
4. **Metrics**: Track success rates, common errors, etc.
5. **Testing**: Verify detector/planner/executor behavior

## Future Enhancements

Possible future additions to the JSON:

- **Timing information**: How long each stage took
- **Git state snapshot**: What files were deleted at this iteration
- **Executor logs**: Detailed stdout/stderr from git commands
- **Plan ranking**: Why one plan was chosen over another
- **Confidence scoring**: Aggregate confidence across all clues

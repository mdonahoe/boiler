# Quick Reference: New Pipeline System

## Files Created

```
pipeline/                           # New 3-stage system
├── models.py                       # Data structures
├── pipeline.py                     # Orchestration
├── handlers.py                     # Registration
├── detectors/                      # Stage 1
├── planners/                       # Stage 2
└── executors/                      # Stage 3

analyze_legacy_handlers.py          # Analysis tool
test_pipeline.py                    # Tests
test_legacy_tracking.py             # Tests
```

## Debug Output Files

```
.boil/
├── iter1.exit127.txt               # Raw stderr/stdout (existing)
├── iter1.pipeline.json             # NEW: Structured debug info
├── iter2.exit127.txt
├── iter2.pipeline.json
└── ...
```

## JSON Structure

```json
{
  "success": true/false,
  "files_modified": ["file1.py", "file2.py"],
  "error_message": "error or null",
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
      "plan_type": "restore_file",
      "priority": 0,
      "target_file": "./test.py",
      "action": "restore_full",
      "params": {"ref": "HEAD"},
      "reason": "Human-readable explanation"
    }
  ],
  "plans_attempted": [...],
  "legacy_handler_used": "handle_name_error" // or null
}
```

## Key Commands

```bash
# Run boil with new pipeline
python3 boil.py -n 10 ./my_test_command

# Analyze legacy handler usage
python3 analyze_legacy_handlers.py

# View debug JSON (requires jq)
cat .boil/iter1.pipeline.json | jq .

# See what was detected
cat .boil/iter*.pipeline.json | jq '.clues_detected'

# See which legacy handlers were used
cat .boil/iter*.pipeline.json | jq '.legacy_handler_used' | sort | uniq -c

# Check success rate
grep -o '"success": [^,]*' .boil/iter*.pipeline.json | cut -d' ' -f2 | sort | uniq -c
```

## Console Output

### When Pipeline Succeeds

```
[Pipeline] Attempting repair with new pipeline system...
[Detector:PermissionDeniedDetector] Found 1 clue(s)
[Planner:PermissionFixPlanner] Generated 1 plan(s)
[Executor:GitRestoreExecutor] Executing: restore_full on ./test.py
[Pipeline] Success: fixed with pipeline (modified 1 file(s))
[Pipeline] Debug info saved to .boil/iter1.pipeline.json
```

### When Pipeline Fails, Legacy Handler Used

```
[Pipeline] Attempting repair with new pipeline system...
[Pipeline] Pipeline did not produce a fix, falling back to old handlers...
[Legacy] Used legacy handler: handle_name_error
[Pipeline] Debug info saved to .boil/iter1.pipeline.json
```

## Current Status

- ✅ 1 handler migrated: `handle_permission_denied`
- ✅ 70+ handlers remaining (as fallback)
- ✅ JSON debug output working
- ✅ Legacy handler tracking working
- ✅ Analysis tool working

## Migration Priority (Example)

After running your test suite:

```bash
$ python3 analyze_legacy_handlers.py
```

Output shows:
```
1. handle_name_error        (8 times)  ← Migrate this first
2. handle_import_error1     (3 times)  ← Then this
3. handle_missing_file      (2 times)  ← Then this
```

## Next Steps

1. **Run test suite**: `python3 boil.py -n 50 ./my_tests`
2. **Analyze results**: `python3 analyze_legacy_handlers.py`
3. **Migrate top handlers**: Use MIGRATION_GUIDE.md
4. **Re-run**: See improvement in success rate

## Documentation

- `REFACTORING_PLAN.md` - Architecture overview
- `REFACTOR_STATUS.md` - Current status
- `MIGRATION_GUIDE.md` - How to migrate handlers
- `DEBUG_JSON_EXAMPLE.md` - JSON examples
- `LEGACY_HANDLER_TRACKING.md` - Legacy tracking feature
- `FEATURE_SUMMARY.md` - What was added
- `QUICK_REFERENCE.md` - This file

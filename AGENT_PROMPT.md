# AI Agent Prompt for Improving Boiler

Use this prompt when asking an AI agent to analyze a target repo's `.boil` folder and fix boiler to handle those errors.

## Full Prompt

```
# Analyze .boil folder and improve boiler

Analyze the debugging information in [TARGET_REPO]/.boil/ and improve boiler to handle those errors correctly.

## Steps

1. **Analyze the errors**
   - Read all JSON files in [TARGET_REPO]/.boil/ (especially iter*.pipeline.json)
   - Run: `python3 ~/boiler/analyze_legacy_handlers.py` from TARGET_REPO
   - Identify which error types are using legacy handlers (not detected by pipeline)
   - For each error type, understand:
     - What the error looks like (the stderr/stdout pattern)
     - What file needs to be fixed
     - What the fix should be

2. **Create pipeline components** (in ~/boiler)
   - If no detector exists for this error:
     - Create a detector in `pipeline/detectors/` that matches the error pattern
     - Extract the relevant context (file path, error details, etc.)
   - If the detector exists but planner doesn't:
     - Create a planner in `pipeline/planners/` that generates repair plans
   - If executor doesn't exist:
     - Create an executor in `pipeline/executors/` that performs the fix
   - Register all new components in `pipeline/handlers.py`

3. **Add tests**
   - Create unit tests in `tests/` for the new detector/planner
   - Tests should cover:
     - Detection of the error pattern
     - Planning for different file states
     - Proper handling of edge cases

4. **Validate**
   - Run `make test` in boiler - all tests must pass
   - Test on [TARGET_REPO]:
     - Reset to pre-boil state: `boil --abort` (restores working directory and removes .boil)
     - Run: `boil [test-command]` or `python3 ~/boiler/boil.py [test-command]`
     - Verify it fixes the errors without infinite loops
     - After testing, if the repo is now fixed, you can use `boil --abort` again to return to the broken state for another test iteration

5. **Document**
   - Update `notes/` with what was added and why
   - Update `README.md` if needed with new error types

## Tips

- Look for patterns: errors with similar root causes might use the same detector/planner
- Use src_repair when restoring code elements, not for full file restoration
- Planners should only create plans for files they can actually fix
- Executors should validate before attempting fixes
- **Understanding boil --abort**: This command resets the repository to its pre-boil state (the state when boil was first started), which is often a broken state with deleted files or errors. This is useful for:
  - Testing your fixes from a clean slate
  - Iterating on improvements (abort → make changes → test again)
  - After a successful boil run, if you want to test improvements without re-breaking the repo manually
```

## Usage

Replace `[TARGET_REPO]` with the actual path:

```
# Analyze .boil folder and improve boiler

Analyze the debugging information in /root/dim/.boil/ and improve boiler to handle those errors correctly.

[rest of prompt above]
```

## Short One-Liner

Use this when talking to an AI agent:

```
Follow ~/boiler/AGENT_PROMPT.md and apply it to [TARGET_REPO]/.boil/
```

Example:
```
Follow ~/boiler/AGENT_PROMPT.md and apply it to /root/dim/.boil/
```

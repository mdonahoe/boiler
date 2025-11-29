# AI Agent Prompt for Improving Boiler

Use this prompt when asking an AI agent to analyze a target repo's `.boil` folder and fix boiler to handle those errors.

## Full Prompt

```
# Analyze .boil folder and improve boiler

Analyze the debugging information in [TARGET_REPO]/.boil/ and improve boiler to handle those errors correctly.

## Steps

1. **Analyze the errors**
   - The user has likely run into an issue and is asking for your help to improve boiler until it can repair the target repo.
   - Run `~/boiler/analyze_boil_logs.py` from within the target repo to check the status of the current boiling session. This will give you a summary.
   - For full details, read all JSON files in [TARGET_REPO]/.boil/ (especially iter*.pipeline.json)
   - Look for errors where boiler was unable to handle a particular error, and see if you can write a new detector or planner to handle it.
   - For each error type, understand:
     - What the error looks like (the stderr/stdout pattern)
     - What file needs to be fixed
     - What the fix should be
   - Use `boil --handle-error <path-to-err-text-file>` to test your new code on a particular error output.
        For example: `boil --handle-error ~/.boil/iter1.exit1.txt`
   - If there are a lot of iter files, see if boiler is stuck in an infinite loop and try to fix it.
   - If boiling had succeeded, identify which error types are using legacy handlers (not detected by pipeline) and migrate them to pipeline format.

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

## Tips for Detector/Planner Implementation

### Critical: Always Validate Repairs
**Every executor must verify that repairs actually modified files.** Capture file state before and after, and return failure if unchanged. Without this, false "successes" cause infinite loops.

### Detector Best Practices
1. **Filter out stdlib vs project code**: Maintain lists of known stdlib functions/constants to avoid attempting restoration of standard library symbols
2. **Match compiler output carefully**: Handle both ASCII and Unicode quotes in error messages (GCC uses U+2018/U+2019 for smart quotes)
3. **Look for include suggestions first**: Compiler hints like "include '<stdio.h>'" are reliable indicators of missing headers

### Planner Best Practices
1. **Be generic, not repo-specific**: Never hardcode filenames or paths. Use git state (modified files, deleted files) for dynamic prioritization
2. **Prioritize by impact**: Modified files in root directory are likely compilation targets; use scoring system rather than hardcoded patterns
3. **Only create plans for fixable issues**: Don't plan repairs for missing headers (src_repair can't add includes)
4. **Avoid duplicates**: Track which symbols/files already have plans to prevent redundant repairs

### Executor Best Practices
1. **Verify changes happened**: Compare file content/hash before and after repair
2. **Report specific failures**: "File unchanged" is more useful than generic errors
3. **Let tools handle what they're designed for**: src_repair knows how to restore code; don't second-guess it with pre-checks

### Understanding boil --abort
This command resets the repository to its pre-boil state (the state when boil was first started), which is often a broken state with deleted files or errors. This is useful for:
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

Users should use this when talking to an AI agent:

```
Follow ~/boiler/AGENT_PROMPT.md and apply it to [TARGET_REPO]/.boil/
```

Example:
```
Follow ~/boiler/AGENT_PROMPT.md and apply it to /root/dim/.boil/
```

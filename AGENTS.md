# AI Agent Prompt for Improving Boiler

Use this prompt when asking an AI agent to analyze a target repo's `.boil` folder and fix boiler to handle those errors.

## Full Prompt

```
# Analyze .boil folder and improve boiler

Analyze the debugging information in [TARGET_REPO]/.boil/ and improve boiler to handle those errors correctly.

## Steps

1. **Analyze the errors**
   - The user has likely run into an issue and is asking for your help to improve boiler until it can repair the target repo.
   - Run `boil --check` from within the target repo to check the status of the current boiling session. This will give you a summary.
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
   - Run `make check` in boiler - this is fast but not comprehensive.
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

### CRITICAL: When Tests Fail During "make check"

**NEVER modify tests to make them pass. Fix your implementation instead.**

If `make check` fails:
1. **Read the error message carefully** - it tells you what's wrong
2. **Fix the IMPLEMENTATION code** (detectors/planners/executors), NOT the test
3. **Commit test changes separately** - if you need to update a test, commit it BEFORE making implementation changes

Common test failures and what they mean:
- `INTEGRITY CHECK FAILED: Test files have been modified` - You modified a test file. Revert it and fix your code instead.
- `HARD-CODED LIBRARY KEYWORDS DETECTED IN PLANNERS` - You hard-coded library-specific logic (like `tree_sitter` or `TSLanguage`). Make your planner generic using git history instead.
- `Detected inefficient regex patterns` - Your regex has multiple lazy quantifiers that cause exponential backtracking. Rewrite the pattern.

**Why tests catch you trying to cheat:**
- Tests have integrity checks that detect modifications
- Tests scan for hard-coded library names
- These safeguards prevent brittle, repo-specific code

### Critical: Always Validate Repairs
**Every executor must verify that repairs actually modified files.** Capture file state before and after, and return failure if unchanged. Without this, false "successes" cause infinite loops.

### Detector Best Practices
1. **Filter out stdlib vs project code**: Maintain lists of known stdlib functions/constants to avoid attempting restoration of standard library symbols
2. **Match compiler output carefully**: Handle both ASCII and Unicode quotes in error messages (GCC uses U+2018/U+2019 for smart quotes)
3. **Look for include suggestions first**: Compiler hints like "include '<stdio.h>'" are reliable indicators of missing headers
4. **Use generic patterns**: Don't hard-code library-specific strings. If you find yourself writing `if "tree_sitter" in ...`, you're doing it wrong.

### Planner Best Practices

**CRITICAL: Planners Must Be Generic**

Your planner should work for ANY C library (tree-sitter, libpng, OpenSSL, custom code), not just one specific library.

**❌ BAD (Hard-coded):**
```python
TYPE_TO_HEADER = {
    "TSLanguage": "tree-sitter/lib/include/tree_sitter/api.h",
    "TSParser": "tree-sitter/lib/include/tree_sitter/api.h",
}
if type_name in TYPE_TO_HEADER:
    return TYPE_TO_HEADER[type_name]
```
This only works for tree-sitter. Tests will catch this and fail.

**✅ GOOD (Generic using git history):**
```python
def find_header_for_type(type_name: str, git_state: GitState) -> str:
    # 1. Search git history for this type name
    result = subprocess.run(
        ['git', 'grep', type_name, 'HEAD', '--', '*.h'],
        capture_output=True, text=True
    )

    # 2. Parse which header files define this type
    headers = parse_git_grep_output(result.stdout)

    # 3. Check if those headers are corrupted/empty NOW
    for header in headers:
        if is_corrupted_or_empty(header):
            return header

    return None
```
This works for ANY library by asking git "where is this type defined?"

**Generic Planner Strategy:**
1. **Use git history as source of truth**: `git grep <type_name> HEAD -- '*.h'` finds where types are defined
2. **Never hard-code library names**: No `"tree_sitter"`, `"TSLanguage"`, or specific paths
3. **Infer from patterns**: If multiple types are missing from the same file, that file is likely corrupted
4. **Check current state**: Compare git history (where type was defined) vs current file (is it empty/corrupted?)

**Other Planner Best Practices:**
1. **Prioritize by impact**: Modified files in root directory are likely compilation targets; use scoring system rather than hardcoded patterns
2. **Only create plans for fixable issues**: Don't plan repairs for missing headers (src_repair can't add includes)
3. **Avoid duplicates**: Track which symbols/files already have plans to prevent redundant repairs

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
Follow ~/boiler/AGENTS.md and apply it to [TARGET_REPO]/.boil/
```

Example:
```
Follow ~/boiler/AGENTS.md and apply it to /root/dim/.boil/
```

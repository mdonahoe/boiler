# Migration Guide: Old Handlers → New Pipeline

This guide shows how to migrate existing handlers from `handlers.py` to the new 3-stage pipeline system.

## Quick Reference

| Old System | New System |
|------------|------------|
| Single function does everything | 3 separate components: Detector → Planner → Executor |
| 50-100 lines per handler | 10-20 lines per component |
| Hard to test | Each component testable independently |
| No validation | Executors validate all operations |
| First match wins | All detectors run, plans sorted by priority |

## Example Migration: handle_permission_denied

### Old System (70 lines)

```python
def handle_permission_denied(err: str) -> bool:
    """Handle the case where a file exists but doesn't have execute permissions."""
    # Check for PermissionError prefix (from run_command exception)
    # or standard "Permission denied" message
    if "PermissionError:" not in err and "Permission denied" not in err:
        return False

    # Extract the file path from the error message
    # Formats:
    #   PermissionError: [Errno 13] Permission denied: './test_tree_print.py'
    #   Permission denied: './test_tree_print.py'
    #   /bin/sh: 1: ./testty.py: Permission denied
    match = re.search(r"Permission denied:\s*['\"]?([^'\"]+)['\"]?", err)
    if not match:
        # Try the /bin/sh format: "path: Permission denied"
        match = re.search(r":\s*([^\s:]+):\s*Permission denied", err)

    if not match:
        print("Could not extract file path from permission error")
        return False

    file_path = match.group(1).strip()
    print(f"Permission denied for: {file_path}")

    # If this is a modified file (not deleted), restore it from git
    # to get the correct permissions
    relative_path = os.path.relpath(file_path) if os.path.isabs(file_path) else file_path

    # Check if the file exists
    if not os.path.exists(relative_path):
        print(f"File {relative_path} does not exist, trying to restore")
        return restore_missing_file(relative_path)

    # File exists but has wrong permissions - restore from git
    print(f"File exists but has wrong permissions, restoring from git")
    try:
        git_toplevel = get_git_toplevel()
        cwd = os.getcwd()

        # Convert relative path to git-root-relative path for git checkout
        abs_path = os.path.abspath(relative_path)
        git_relative_path = os.path.relpath(abs_path, git_toplevel)

        subprocess.check_call(["git", "-C", git_toplevel, "checkout", "HEAD", "--", git_relative_path])
        print(f"Successfully restored {relative_path} with correct permissions from git")
        return True
    except subprocess.CalledProcessError:
        print(f"Failed to restore {relative_path} from git")
        return False
```

### New System (3 components, ~40 lines total)

#### 1. Detector (15 lines)

```python
class PermissionDeniedDetector(Detector):
    """Detect permission denied errors."""

    @property
    def name(self) -> str:
        return "PermissionDeniedDetector"

    def detect(self, stderr: str, stdout: str = "") -> List[ErrorClue]:
        combined = stderr + "\n" + stdout
        if "PermissionError:" not in combined and "Permission denied" not in combined:
            return []

        clues = []
        pattern = r"Permission denied:\s*['\"]?([^'\"]+)['\"]?"
        for match in re.finditer(pattern, combined):
            file_path = match.group(1).strip()
            clues.append(ErrorClue(
                clue_type="permission_denied",
                confidence=1.0,
                context={"file_path": file_path},
                source_line=match.group(0)
            ))
        return clues
```

#### 2. Planner (25 lines)

```python
class PermissionFixPlanner(Planner):
    """Plan fixes for permission denied errors."""

    @property
    def name(self) -> str:
        return "PermissionFixPlanner"

    def can_handle(self, clue_type: str) -> bool:
        return clue_type == "permission_denied"

    def plan(self, clue: ErrorClue, git_state: GitState) -> List[RepairPlan]:
        file_path = clue.context.get("file_path")
        if not file_path:
            return []

        if os.path.isabs(file_path):
            file_path = os.path.relpath(file_path)

        if not os.path.exists(file_path):
            priority = 0  # High priority - file missing
            reason = f"File {file_path} is missing"
        else:
            priority = 1  # Medium priority - file exists
            reason = f"File {file_path} has wrong permissions"

        return [RepairPlan(
            plan_type="restore_permissions",
            priority=priority,
            target_file=file_path,
            action="restore_full",
            params={"ref": git_state.ref},
            reason=reason,
            clue_source=clue
        )]
```

#### 3. Executor (Shared - already exists)

The `GitRestoreExecutor` can handle all git restore operations, so we don't need to write a new executor. It already validates and executes the "restore_full" action.

## Migration Steps

### Step 1: Identify Error Pattern

Look at the old handler and identify:
- What error patterns does it match?
- What information does it extract?
- What actions does it take?

Example from `handle_permission_denied`:
- Pattern: "Permission denied" or "PermissionError:"
- Extracts: file path
- Action: git checkout to restore file

### Step 2: Create Detector

Create a new detector in `pipeline/detectors/` that matches the error pattern:

```python
class MyErrorDetector(Detector):
    @property
    def name(self) -> str:
        return "MyErrorDetector"

    def detect(self, stderr: str, stdout: str = "") -> List[ErrorClue]:
        # Early exit if pattern not present
        if "my_error_keyword" not in stderr:
            return []

        clues = []
        # Extract relevant information with regex
        for match in re.finditer(r"my_pattern", stderr):
            clues.append(ErrorClue(
                clue_type="my_error_type",
                confidence=1.0,
                context={"key": "value"},
                source_line=match.group(0)
            ))
        return clues
```

### Step 3: Create Planner

Create a planner in `pipeline/planners/` that converts clues into repair plans:

```python
class MyFixPlanner(Planner):
    @property
    def name(self) -> str:
        return "MyFixPlanner"

    def can_handle(self, clue_type: str) -> bool:
        return clue_type == "my_error_type"

    def plan(self, clue: ErrorClue, git_state: GitState) -> List[RepairPlan]:
        # Extract context from clue
        info = clue.context.get("key")

        # Determine priority
        # 0 = critical (missing files)
        # 1 = high (wrong permissions)
        # 2 = medium (missing symbols)
        # 3+ = low
        priority = 0

        # Choose action
        # "restore_full" - git checkout entire file
        # "restore_symbol" - py_repair with specific symbol
        action = "restore_full"

        return [RepairPlan(
            plan_type="my_plan_type",
            priority=priority,
            target_file="path/to/file",
            action=action,
            params={"ref": git_state.ref, "other": "params"},
            reason="Human-readable explanation",
            clue_source=clue
        )]
```

### Step 4: Create Executor (if needed)

Only create a new executor if existing ones don't handle your action:

Existing executors:
- `GitRestoreExecutor`: handles "restore_full" (git checkout)

If you need a new executor:

```python
class MyExecutor(Executor):
    @property
    def name(self) -> str:
        return "MyExecutor"

    def can_handle(self, action: str) -> bool:
        return action == "my_action"

    def validate_plan(self, plan: RepairPlan) -> Tuple[bool, Optional[str]]:
        # Validate plan before execution
        # Return (True, None) if valid
        # Return (False, "error message") if invalid
        return (True, None)

    def execute(self, plan: RepairPlan) -> RepairResult:
        try:
            # Perform the action
            # ...
            return RepairResult(
                success=True,
                plans_attempted=[plan],
                files_modified=["file.py"],
                error_message=None
            )
        except Exception as e:
            return RepairResult(
                success=False,
                plans_attempted=[plan],
                files_modified=[],
                error_message=str(e)
            )
```

### Step 5: Register

Add to `pipeline/handlers.py`:

```python
from pipeline.detectors.my_module import MyErrorDetector
from pipeline.planners.my_module import MyFixPlanner
from pipeline.executors.my_module import MyExecutor  # if new

def register_all_handlers():
    # ... existing registrations ...
    register_detector(MyErrorDetector())
    register_planner(MyFixPlanner())
    register_executor(MyExecutor())  # if new
```

### Step 6: Test

Create a test in `test_pipeline.py`:

```python
def test_my_error():
    """Test that my error is detected and fixed"""
    register_all_handlers()

    stderr = "my error message here"
    git_state = GitState(ref="HEAD", deleted_files=set(), git_toplevel="/root/boiler")

    result = run_pipeline(stderr, "", git_state, debug=True)

    assert result.success
    assert len(result.files_modified) > 0
```

## Common Patterns

### Pattern 1: Missing File

Many handlers restore missing files. Use `MissingFilePlanner` (already exists):

```python
# In your detector:
return [ErrorClue(
    clue_type="missing_file",  # Use this type
    confidence=1.0,
    context={"file_path": "path/to/file"},
    source_line=match.group(0)
)]

# MissingFilePlanner will automatically handle it!
```

### Pattern 2: Python Symbol Restoration

For Python NameError, ImportError, etc., we need a new `PythonSymbolPlanner`:

```python
class PythonSymbolPlanner(Planner):
    """Plan py_repair operations for Python symbol errors."""

    def plan(self, clue: ErrorClue, git_state: GitState) -> List[RepairPlan]:
        file_path = clue.context.get("file_path")
        symbol = clue.context.get("symbol")

        return [RepairPlan(
            plan_type="restore_symbol",
            priority=2,  # Medium priority
            target_file=file_path,
            action="restore_symbol",
            params={"ref": git_state.ref, "missing": symbol},
            reason=f"Restore missing symbol '{symbol}' in {file_path}",
            clue_source=clue
        )]
```

And a `PyRepairExecutor`:

```python
class PyRepairExecutor(Executor):
    """Execute py_repair operations."""

    def can_handle(self, action: str) -> bool:
        return action == "restore_symbol"

    def execute(self, plan: RepairPlan) -> RepairResult:
        import py_repair
        try:
            py_repair.repair(
                filename=plan.target_file,
                commit=plan.params["ref"],
                missing=plan.params.get("missing"),
                verbose=False
            )
            return RepairResult(
                success=True,
                plans_attempted=[plan],
                files_modified=[plan.target_file],
                error_message=None
            )
        except Exception as e:
            return RepairResult(
                success=False,
                plans_attempted=[plan],
                files_modified=[],
                error_message=str(e)
            )
```

### Pattern 3: Directory Restoration

Some handlers restore entire directories. Create a `DirectoryRestorePlanner`.

## Priority Guidelines

Use these priorities for consistency:

- **0**: Critical - missing files that block execution
- **1**: High - wrong permissions, missing executables
- **2**: Medium - missing Python symbols (classes, functions)
- **3**: Low - missing imports (can be inferred)
- **4+**: Very low - optional features

## Testing Guidelines

For each migrated handler:

1. Test detection with positive cases (should detect)
2. Test detection with negative cases (should not detect)
3. Test planning produces correct priorities
4. Test execution validates properly
5. Test execution handles errors gracefully

## Rollback Plan

If a migrated handler causes issues:

1. The old handler is still in `handlers.py` as fallback
2. Comment out registration in `pipeline/handlers.py`
3. Old handler will take over automatically

## Progress Tracking

Use this checklist as you migrate:

- [ ] `handle_permission_denied` ✓ (DONE)
- [ ] `handle_missing_file`
- [ ] `handle_executable_not_found`
- [ ] `handle_file_not_found`
- [ ] `handle_cat_no_such_file`
- [ ] `handle_diff_no_such_file`
- [ ] `handle_sh_cannot_open`
- [ ] `handle_sh_cant_cd`
- [ ] `handle_shell_command_not_found`
- [ ] `handle_name_error` (needs PyRepairExecutor)
- [ ] `handle_import_error1`
- [ ] `handle_import_error2`
- [ ] `handle_import_name_error`
- [ ] `handle_module_attribute_error`
- [ ] `handle_object_attribute_error`
- [ ] ... (70+ total)

## Questions?

See `REFACTORING_PLAN.md` for architecture details.
See `REFACTOR_STATUS.md` for current status.

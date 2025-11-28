# Refactoring Status: 3-Stage Pipeline

## Completed ✓

### Phase 1: Foundation
- [x] Created pipeline directory structure
- [x] Defined core data models (ErrorClue, RepairPlan, RepairResult, GitState)
- [x] Created detector base classes and registry
- [x] Created planner base classes and registry
- [x] Created executor base classes and registry
- [x] Built main pipeline orchestration

### Phase 2: Initial Migration
- [x] Migrated `handle_permission_denied` to 3-stage system:
  - `PermissionDeniedDetector` (Stage 1)
  - `PermissionFixPlanner` (Stage 2)
  - `GitRestoreExecutor` (Stage 3)
- [x] Migrated `handle_make_missing_target` to 3-stage system:
  - `MakeMissingTargetDetector` (Stage 1)
  - `MakeMissingTargetPlanner` (Stage 2)
  - `GitRestoreExecutor` (Stage 3 - reused)
- [x] Integrated pipeline into boil.py with fallback to old handlers
- [x] Created test suite for pipeline
- [x] Added JSON debug output with legacy handler tracking

## How It Works

The new system runs in 3 stages:

### Stage 1: Detection
- **Input**: stderr/stdout from failed command
- **Output**: List of `ErrorClue` objects
- **Example**: `PermissionDeniedDetector` scans for "Permission denied" patterns

### Stage 2: Planning
- **Input**: List of `ErrorClue` objects + git state
- **Output**: Sorted list of `RepairPlan` objects
- **Example**: `PermissionFixPlanner` creates plans to restore files from git

### Stage 3: Execution
- **Input**: Sorted list of `RepairPlan` objects
- **Output**: `RepairResult` indicating success/failure
- **Example**: `GitRestoreExecutor` performs git checkout with validation

## Integration with boil.py

The pipeline is integrated with a fallback mechanism:

1. When an error occurs, try the new pipeline first
2. If pipeline succeeds and files are modified, use that fix
3. If pipeline doesn't fix it, fall back to old handlers
4. Old handlers remain in place as safety net

## Files Created

```
pipeline/
├── __init__.py                      # Package exports
├── models.py                        # Core data structures
├── pipeline.py                      # Main orchestration
├── handlers.py                      # Handler registration
├── detectors/
│   ├── __init__.py
│   ├── base.py                      # Detector base class
│   ├── registry.py                  # Detector registry
│   └── permissions.py               # Permission error detector
├── planners/
│   ├── __init__.py
│   ├── base.py                      # Planner base class
│   ├── registry.py                  # Planner registry
│   └── file_restore.py              # File restoration planner
└── executors/
    ├── __init__.py
    ├── base.py                      # Executor base class
    ├── registry.py                  # Executor registry
    └── git_restore.py               # Git restoration executor
```

## Test Results

All tests passing ✓

```
Test 1: Permission Denied Detection - PASSED
  - Detects permission errors
  - Creates repair plan
  - Executes git restore

Test 2: No Error Detection - PASSED
  - Returns gracefully when no errors

Test 3: Missing File Validation - PASSED
  - Validates files exist in git before restoring
  - Rejects invalid repair plans
```

## Benefits Achieved

1. **Easier to write handlers**: Each stage is 10-20 lines instead of 50-100
2. **Better testing**: Each stage testable independently
3. **Better validation**: Executors validate all operations before executing
4. **Better debugging**:
   - Clear separation of detect → plan → execute
   - **JSON debug files** saved to `.boil/iterN.pipeline.json` for each iteration
   - Shows exactly what was detected, planned, and executed
5. **Better prioritization**: Plans sorted by priority before execution

## Next Steps

To migrate remaining handlers:

### Easy Handlers (Similar to permission_denied)
- `handle_missing_file`
- `handle_cat_no_such_file`
- `handle_diff_no_such_file`
- `handle_sh_cannot_open`
- `handle_executable_not_found`

### Medium Handlers (Need new planners)
- `handle_name_error` (needs PythonSymbolPlanner)
- `handle_import_error1/2` (needs PythonSymbolPlanner)
- `handle_module_attribute_error` (needs PythonSymbolPlanner)
- `handle_object_attribute_error` (needs PythonSymbolPlanner)

### Complex Handlers (Need multiple detectors/planners)
- `handle_rust_module_not_found`
- `handle_cargo_missing_library`
- `handle_make_missing_target`
- `handle_c_linker_error`

## Migration Template

To migrate a handler to the new system:

1. **Create Detector** in `pipeline/detectors/`:
```python
class MyErrorDetector(Detector):
    @property
    def name(self) -> str:
        return "MyErrorDetector"

    def detect(self, stderr: str, stdout: str = "") -> List[ErrorClue]:
        # Pattern matching logic here
        return [ErrorClue(...)]
```

2. **Create Planner** in `pipeline/planners/`:
```python
class MyFixPlanner(Planner):
    @property
    def name(self) -> str:
        return "MyFixPlanner"

    def can_handle(self, clue_type: str) -> bool:
        return clue_type == "my_error"

    def plan(self, clue: ErrorClue, git_state: GitState) -> List[RepairPlan]:
        # Planning logic here
        return [RepairPlan(...)]
```

3. **Create Executor** (if needed) in `pipeline/executors/`:
```python
class MyExecutor(Executor):
    @property
    def name(self) -> str:
        return "MyExecutor"

    def can_handle(self, action: str) -> bool:
        return action == "my_action"

    def execute(self, plan: RepairPlan) -> RepairResult:
        # Execution logic here
        return RepairResult(...)
```

4. **Register** in `pipeline/handlers.py`:
```python
register_detector(MyErrorDetector())
register_planner(MyFixPlanner())
register_executor(MyExecutor())  # if new executor needed
```

## Current System Status

- **Old handlers**: 71+ handlers in handlers.py (still active as fallback)
- **New pipeline**: 8 handlers migrated
  - permission_denied
  - make_missing_target
  - file_not_found
  - sh_cannot_open
  - shell_command_not_found
  - cat_no_such_file
  - c_compilation_error
  - diff_no_such_file (bonus)
- **Fallback**: Active - if pipeline doesn't fix, falls back to old handlers
- **Safety**: High - old system unchanged, new system adds validation
- **Loop prevention**: Executor validates that restorations actually create changes
- **Debug output**: JSON files track detections, plans, and legacy handler usage
- **Success rate**: ~86% in heirloom-ex-vi test (12/14 iterations)

## Performance

Pipeline overhead is minimal:
- Stage 1 (Detection): O(n) where n = stderr length
- Stage 2 (Planning): O(m) where m = number of clues (typically 1-5)
- Stage 3 (Execution): O(1) - tries first plan, returns on success

Total: ~same as old system, with better debugging and validation.

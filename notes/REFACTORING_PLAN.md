# Boiler Refactoring Plan: Multi-Stage Handler Architecture

## Problem Statement

Currently, handlers in `handlers.py` are monolithic functions that:
1. Match error patterns in stderr
2. Determine which files might be affected
3. Directly modify the working directory (restore files or call `do_repair`)

This tight coupling makes handlers:
- **Hard to write**: Must handle all 3 concerns in one function
- **Hard to test**: Cannot test pattern matching independently from file operations
- **Hard to order**: Cannot prioritize fixes across different handler types
- **Risky**: Handlers can make arbitrary edits without validation

## Proposed Architecture: 3-Stage Pipeline

### Stage 1: Error Detection & Classification
**Input**: stderr/stdout text
**Output**: List of `ErrorClue` objects

```python
@dataclasses.dataclass
class ErrorClue:
    """Evidence of a specific error type found in stderr"""
    clue_type: str  # e.g., "permission_error", "missing_file", "name_error"
    confidence: float  # 0.0-1.0, how confident we are this is the right error
    context: Dict[str, str]  # extracted details (file_path, symbol_name, etc.)
    source_line: str  # the actual error line that triggered this clue
```

**Detectors**: Simple pattern-matching functions
```python
def detect_permission_error(stderr: str) -> List[ErrorClue]:
    """Look for PermissionError keywords"""
    clues = []
    for match in re.finditer(r"Permission denied:\s*['\"]?([^'\"]+)['\"]?", stderr):
        clues.append(ErrorClue(
            clue_type="permission_error",
            confidence=1.0,
            context={"file_path": match.group(1)},
            source_line=match.group(0)
        ))
    return clues
```

### Stage 2: Repair Planning
**Input**: List of `ErrorClue` objects + git state
**Output**: List of `RepairPlan` objects (sorted by priority)

```python
@dataclasses.dataclass
class RepairPlan:
    """A proposed fix for an error"""
    plan_type: str  # "restore_file", "repair_symbol", "restore_permissions"
    priority: int  # Lower = higher priority (0 = must fix first)
    target_file: str  # file to modify (relative to cwd)
    action: str  # "restore_full", "restore_symbol", "restore_permissions"
    params: Dict[str, Any]  # action-specific parameters
    reason: str  # human-readable explanation
    clue_source: ErrorClue  # the clue that generated this plan
```

**Planners**: Convert clues into concrete repair plans
```python
def plan_permission_fix(clue: ErrorClue, git_state: GitState) -> List[RepairPlan]:
    """Convert permission error clue into repair plan"""
    file_path = clue.context["file_path"]

    if not os.path.exists(file_path):
        # File missing entirely - restore it
        return [RepairPlan(
            plan_type="restore_file",
            priority=0,  # High priority - missing file
            target_file=file_path,
            action="restore_full",
            params={"ref": git_state.ref},
            reason=f"File {file_path} is missing",
            clue_source=clue
        )]
    else:
        # File exists but wrong permissions - restore from git
        return [RepairPlan(
            plan_type="restore_permissions",
            priority=1,  # Medium priority - file exists
            target_file=file_path,
            action="restore_full",
            params={"ref": git_state.ref},
            reason=f"File {file_path} has wrong permissions",
            clue_source=clue
        )]
```

### Stage 3: Repair Execution
**Input**: Sorted list of `RepairPlan` objects
**Output**: `RepairResult` object

```python
@dataclasses.dataclass
class RepairResult:
    """The outcome of attempting repairs"""
    success: bool
    plans_attempted: List[RepairPlan]
    files_modified: List[str]
    error_message: Optional[str]
```

**Executors**: Safe, validated file operations
```python
def execute_repair(plan: RepairPlan) -> RepairResult:
    """Execute a repair plan with validation"""
    if plan.action == "restore_full":
        return execute_restore_full(plan)
    elif plan.action == "restore_symbol":
        return execute_restore_symbol(plan)
    else:
        raise ValueError(f"Unknown action: {plan.action}")

def execute_restore_full(plan: RepairPlan) -> RepairResult:
    """Restore entire file from git"""
    # Validate: file must exist in git at ref
    ref = plan.params["ref"]
    if not file_exists_in_git(plan.target_file, ref):
        return RepairResult(
            success=False,
            plans_attempted=[plan],
            files_modified=[],
            error_message=f"File {plan.target_file} not in git at {ref}"
        )

    # Restore from git
    git_checkout(plan.target_file, ref=ref)

    return RepairResult(
        success=True,
        plans_attempted=[plan],
        files_modified=[plan.target_file],
        error_message=None
    )
```

## Implementation Plan

### Phase 1: Foundation (Week 1)
1. **Define core data structures**
   - `ErrorClue`
   - `RepairPlan`
   - `RepairResult`
   - `GitState` helper class

2. **Create stage interfaces**
   - `Detector` protocol/base class
   - `Planner` protocol/base class
   - `Executor` protocol/base class

3. **Build registry system**
   - `DetectorRegistry` to hold all detectors
   - `PlannerRegistry` to map clue types to planners
   - `ExecutorRegistry` to map actions to executors

### Phase 2: Migration (Week 2-3)
1. **Migrate simple handlers first**
   - Start with `handle_permission_denied` (clear semantics)
   - Then `handle_missing_file` (straightforward)
   - Then `handle_cat_no_such_file` (pattern matching only)

2. **Run both systems in parallel**
   - Keep old handlers as fallback
   - New system runs first, falls back to old if no plans generated
   - Compare results in `.boil/` debug logs

3. **Migrate complex handlers**
   - Python-specific handlers (NameError, ImportError, etc.)
   - Build/compile handlers (make, cargo, rust)
   - Test-specific handlers

### Phase 3: Enhancement (Week 4)
1. **Add repair prioritization**
   - Sort plans by priority before execution
   - Try high-priority fixes first (missing files)
   - Lower priority for "nice-to-have" fixes (permissions)

2. **Add repair validation**
   - Check that repairs are subset of git history
   - Validate Python syntax after `py_repair`
   - Ensure no arbitrary edits

3. **Add repair batching**
   - Group related repairs (all missing files in a directory)
   - Execute batch, then re-run test once
   - More efficient than one-at-a-time

### Phase 4: Cleanup (Week 5)
1. **Remove old handler system**
2. **Update documentation**
3. **Add unit tests for each stage**

## File Structure

```
boiler/
├── boil.py                    # Main entry point (updated to use new system)
├── handlers.py                # Old handlers (deprecated, remove in Phase 4)
├── pipeline/
│   ├── __init__.py
│   ├── models.py              # ErrorClue, RepairPlan, RepairResult
│   ├── detectors/
│   │   ├── __init__.py
│   │   ├── base.py            # Detector protocol
│   │   ├── python.py          # Python error detectors
│   │   ├── files.py           # File system error detectors
│   │   ├── permissions.py     # Permission error detectors
│   │   ├── build.py           # Make/cargo/rust detectors
│   │   └── registry.py        # DetectorRegistry
│   ├── planners/
│   │   ├── __init__.py
│   │   ├── base.py            # Planner protocol
│   │   ├── file_restore.py    # Plans for restoring files
│   │   ├── symbol_restore.py  # Plans for py_repair operations
│   │   ├── permission_fix.py  # Plans for permission fixes
│   │   └── registry.py        # PlannerRegistry
│   ├── executors/
│   │   ├── __init__.py
│   │   ├── base.py            # Executor protocol
│   │   ├── git_restore.py     # Execute git checkout operations
│   │   ├── py_repair.py       # Execute py_repair operations
│   │   └── registry.py        # ExecutorRegistry
│   └── pipeline.py            # Main pipeline orchestration
├── py_repair.py               # Existing repair tool (unchanged)
└── session.py                 # Session context (unchanged)
```

## Benefits of New Architecture

### 1. **Easier to Write Handlers**
Old way (70+ lines):
```python
def handle_permission_denied(err: str) -> bool:
    # Parse error (10 lines)
    # Check git state (10 lines)
    # Restore file (20 lines)
    # Handle errors (20 lines)
    # Return success (10 lines)
```

New way (5 lines per stage):
```python
# Detector (5 lines)
def detect_permission_error(stderr: str) -> List[ErrorClue]:
    return [ErrorClue(...) for match in pattern.finditer(stderr)]

# Planner (5 lines)
def plan_permission_fix(clue: ErrorClue) -> List[RepairPlan]:
    return [RepairPlan(...)]

# Executor: shared generic implementation
```

### 2. **Better Testing**
- Test detectors with just error strings
- Test planners with just clues
- Test executors in isolation
- No need for full integration tests for every handler

### 3. **Better Prioritization**
Current system: First handler that matches wins
New system: All detectors run, plans sorted by priority, best fix first

Example: If both "missing file" and "wrong permissions" detected, try restoring file first (higher priority).

### 4. **Better Validation**
- All file operations go through executors
- Executors validate operations are safe
- No arbitrary edits - all changes must be subset of git history
- Easier to audit what changes are being made

### 5. **Better Debugging**
```
.boil/iter5.debug.json:
{
  "clues_detected": [
    {"type": "permission_error", "confidence": 1.0, "file": "test.py"},
    {"type": "missing_file", "confidence": 0.8, "file": "helper.py"}
  ],
  "plans_generated": [
    {"action": "restore_full", "priority": 0, "target": "helper.py"},
    {"action": "restore_permissions", "priority": 1, "target": "test.py"}
  ],
  "plans_executed": [
    {"action": "restore_full", "target": "helper.py", "success": true}
  ]
}
```

## Alternative: Simpler 2-Stage Architecture

If 3 stages seems too complex, here's a simpler 2-stage version:

### Stage 1: Detection
Same as before - detect errors and return clues.

### Stage 2: Execution (combined planning + execution)
```python
@dataclasses.dataclass
class Repair:
    """A repair action to take"""
    action: str  # "restore_file", "repair_symbol"
    target_file: str
    params: Dict[str, Any]
    priority: int

def execute_clue(clue: ErrorClue) -> Optional[Repair]:
    """Convert clue directly into executed repair"""
    if clue.clue_type == "permission_error":
        file_path = clue.context["file_path"]
        git_checkout(file_path)  # Execute immediately
        return Repair(action="restore_file", target_file=file_path, ...)
```

This is simpler but loses some benefits:
- Can't prioritize across different clue types
- Can't validate plans before execution
- Harder to debug (no separation of planning vs execution)

## Recommendation

I recommend the **3-stage architecture** for these reasons:

1. **Your specific concern about preventing arbitrary edits**: Stage 3 executors can validate all changes are subsets of git history. The separation makes this validation clean and auditable.

2. **Sorting fixes before making them**: Stage 2 produces all plans, then we sort by priority, then Stage 3 executes in order. This is exactly what you asked for.

3. **Easier to write handlers**: Each function is 5-10 lines instead of 50-100 lines. New contributors can add a detector without understanding git operations.

4. **Future-proofing**:
   - Want to add dry-run mode? Just skip Stage 3.
   - Want to add user confirmation? Insert between Stage 2 and 3.
   - Want to add ML-based prioritization? Replace Stage 2 sorting logic.
   - Want to support non-git backends? Replace Stage 3 executors.

5. **Matches your proposal**: Your idea of "match keywords → produce candidate files → attempt repairs" maps directly to Stage 1 → Stage 2 → Stage 3.

## Migration Strategy

To minimize risk, I suggest:

1. **Parallel operation**: Run new system alongside old handlers
2. **Gradual migration**: Move 5-10 handlers per week
3. **Validation**: Compare old vs new results in test suite
4. **Fallback**: Keep old handlers as fallback for 1-2 months
5. **Metrics**: Track success rates, iteration counts, debug logs

## Questions for Discussion

1. **Confidence scores**: Should we use confidence (0.0-1.0) for clues, or just binary detection?

2. **Plan ranking**: Should priority be manual (developer-assigned) or automatic (based on clue confidence + file importance)?

3. **Batching**: Should we execute all plans at once, or one-at-a-time with re-testing?

4. **Validation strictness**: Should executors fail loudly on invalid operations, or fall back to safer alternatives?

5. **Language support**: How do we cleanly separate Python-specific logic from general file operations? Should there be a language registry?

## Timeline

- **Week 1**: Foundation (data structures, interfaces, registries)
- **Week 2**: Migrate 10 simple handlers
- **Week 3**: Migrate 20 complex handlers
- **Week 4**: Enhancement (prioritization, validation, batching)
- **Week 5**: Cleanup and documentation

Total: ~5 weeks for complete migration with parallel operation for safety.

## Success Metrics

1. **Handler complexity**: Average lines per handler should drop from ~50 to ~15
2. **Test coverage**: Each stage testable independently (currently only integration tests)
3. **Debug visibility**: Clear JSON logs showing clues → plans → executions
4. **Safety**: All repairs validated as subsets of git history
5. **Performance**: Same or better iteration counts to fix errors

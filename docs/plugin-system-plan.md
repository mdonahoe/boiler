# Plugin System Design Plan

## Goal

Enable AI agents to add new detectors and planners in the target repo's working directory, loaded at runtime without modifying the boiler codebase.

## Current Architecture Summary

Boil is implemented in **Go** with a 3-stage pipeline:
1. **Detectors** - Pattern-match errors, produce `ErrorClue` objects. Already JSON-based via `//go:embed`
2. **Planners** - Convert clues into `RepairPlan` objects using Go logic
3. **Executors** - Execute repair plans (modify files)

Key insight: **Detectors are data-driven** (JSON with patterns/examples), while **planners require code logic**.

## Plugin Location

```
target-repo/
├── .boil/
│   └── plugins/
│       ├── detectors/
│       │   └── my_detector.json      # JSON - easy!
│       └── planners/
│           └── my_planner.star       # Starlark script
```

## Detector Plugins (Easy - JSON)

Detectors are already JSON in Go. Just load from filesystem instead of embed:

```json
{
  "name": "MyErrorDetector",
  "priority": 100,
  "patterns": {
    "my_error": "error: (?P<message>.+)"
  },
  "examples": [
    {
      "name": "basic error",
      "input": "error: something failed",
      "clue_type": "my_error",
      "context": {"message": "something failed"}
    }
  ]
}
```

### Implementation

Add to `src/boil/detectors/json_loader.go`:

```go
// LoadDetectorPlugins loads detector JSON files from .boil/plugins/detectors/
func LoadDetectorPlugins() ([]pipeline.Detector, error) {
    pluginsDir := ".boil/plugins/detectors"
    if _, err := os.Stat(pluginsDir); os.IsNotExist(err) {
        return nil, nil // No plugins directory
    }

    entries, err := os.ReadDir(pluginsDir)
    if err != nil {
        return nil, err
    }

    var detectors []pipeline.Detector
    for _, entry := range entries {
        if entry.IsDir() || filepath.Ext(entry.Name()) != ".json" {
            continue
        }

        data, err := os.ReadFile(filepath.Join(pluginsDir, entry.Name()))
        if err != nil {
            log.Printf("[Plugin] Error reading %s: %v", entry.Name(), err)
            continue
        }

        detector, err := LoadDetectorFromJSONBytes(data)
        if err != nil {
            log.Printf("[Plugin] Error loading %s: %v", entry.Name(), err)
            continue
        }

        if verbose {
            log.Printf("[Plugin] Loaded detector: %s", detector.Name())
        }
        detectors = append(detectors, detector)
    }

    return detectors, nil
}
```

## Planner Plugins (Challenge - Needs Scripting)

Go is compiled, so we can't load `.go` files at runtime. Options:

### Option A: Starlark (Recommended)

[Starlark](https://github.com/google/starlark-go) is a Python-like language designed for configuration/scripting in Go tools (used by Bazel, Buck, etc.).

**Pros:**
- Python-like syntax (familiar to AI agents)
- Safe sandboxed execution
- No external dependencies at runtime
- Deterministic execution

**Example `.boil/plugins/planners/my_planner.star`:**
```python
def name():
    return "MyPlanner"

def can_handle(clue_type):
    return clue_type == "my_error"

def plan(clues, git_state):
    plans = []
    for clue in clues:
        if clue["clue_type"] == "my_error":
            plans.append({
                "plan_type": "restore_file",
                "priority": 10,
                "target_file": find_file_with_error(clue, git_state),
                "action": "restore_full",
                "params": {"ref": git_state["ref"]},
                "reason": "Fix my_error: " + clue["context"]["message"],
            })
    return plans

def find_file_with_error(clue, git_state):
    # Search deleted files for one matching the error
    for f in git_state["deleted_files"]:
        if clue["context"]["message"] in f:
            return f
    return git_state["deleted_files"][0] if git_state["deleted_files"] else ""
```

**Go implementation:**
```go
import "go.starlark.net/starlark"

type StarlarkPlanner struct {
    name      string
    thread    *starlark.Thread
    globals   starlark.StringDict
    canHandle *starlark.Function
    plan      *starlark.Function
}

func LoadPlannerFromStarlark(path string) (*StarlarkPlanner, error) {
    thread := &starlark.Thread{Name: "planner"}
    globals, err := starlark.ExecFile(thread, path, nil, nil)
    if err != nil {
        return nil, err
    }

    // Extract required functions
    nameFunc := globals["name"].(*starlark.Function)
    canHandleFunc := globals["can_handle"].(*starlark.Function)
    planFunc := globals["plan"].(*starlark.Function)

    // Call name() to get planner name
    nameVal, _ := starlark.Call(thread, nameFunc, nil, nil)

    return &StarlarkPlanner{
        name:      nameVal.(starlark.String).GoString(),
        thread:    thread,
        globals:   globals,
        canHandle: canHandleFunc,
        plan:      planFunc,
    }, nil
}
```

### Option B: Lua (Alternative)

Use [gopher-lua](https://github.com/yuin/gopher-lua) for Lua scripting.

**Pros:** Lightweight, fast, battle-tested in games/config
**Cons:** Less familiar syntax than Python

### Option C: JavaScript (goja)

Use [goja](https://github.com/dop251/goja) for JavaScript execution.

**Pros:** Very familiar syntax
**Cons:** Larger runtime, more complexity

### Option D: Python subprocess

Call Python scripts as external processes.

```go
func (p *PythonPlanner) Plan(clues, gitState) ([]*RepairPlan, error) {
    // Serialize input to JSON
    input := map[string]interface{}{
        "clues": clues,
        "git_state": gitState,
    }
    inputJSON, _ := json.Marshal(input)

    // Call Python script
    cmd := exec.Command("python3", p.scriptPath)
    cmd.Stdin = bytes.NewReader(inputJSON)
    output, err := cmd.Output()

    // Parse output JSON
    var plans []*RepairPlan
    json.Unmarshal(output, &plans)
    return plans, nil
}
```

**Pros:** Full Python power, familiar to AI
**Cons:** Requires Python installed, slower, subprocess overhead

## Recommendation: Starlark for Planners

1. **Detectors**: JSON files (already supported, just load from filesystem)
2. **Planners**: Starlark scripts (Python-like, safe, no dependencies)

This gives AI agents a familiar Python-ish syntax while keeping boil as a single Go binary.

## Implementation Steps

### Phase 1: Detector Plugins (JSON)
1. Add `LoadDetectorPlugins()` function to load from `.boil/plugins/detectors/`
2. Call after `RegisterJSONDetectors()` in handlers
3. Test with a sample detector plugin

### Phase 2: Planner Plugins (Starlark)
1. Add `go.starlark.net/starlark` dependency
2. Create `StarlarkPlanner` wrapper type
3. Implement `LoadPlannerPlugins()` to load `.star` files
4. Provide built-in functions for common operations:
   - `git_grep(pattern)` - search git history
   - `read_file(path, ref)` - read file from git
   - `find_deleted_files(pattern)` - filter deleted files
5. Test with sample planner plugins

### Phase 3: Documentation
1. Update AGENTS.md with plugin documentation
2. Add examples in `docs/plugin-examples/`
3. Add `boil --new-detector` and `boil --new-planner` scaffolding commands

## Built-in Functions for Starlark Planners

Provide these as Starlark built-ins:

```python
# Git operations
git_grep(pattern, ref="HEAD")  -> [(file, line_num, content), ...]
git_show(path, ref="HEAD")     -> str
git_log(path, n=10)            -> [commit_info, ...]

# File operations
read_file(path)                -> str or None
file_exists(path)              -> bool
list_dir(path)                 -> [filename, ...]

# Utility
regex_match(pattern, text)     -> {groups...} or None
path_join(*parts)              -> str
path_basename(path)            -> str
path_dirname(path)             -> str
```

## Testing Plan

1. Create test detector plugin JSON in `tests/fixtures/plugins/detectors/`
2. Create test planner plugin Starlark in `tests/fixtures/plugins/planners/`
3. Test plugin discovery and loading
4. Test detector plugins produce correct clues
5. Test planner plugins produce correct plans
6. Integration test: broken repo + plugin that fixes it

## Security Considerations

- Starlark is sandboxed by default (no filesystem/network access)
- We explicitly expose only safe built-in functions
- Plugins run with same permissions as boil itself
- Consider adding resource limits (execution time, memory)

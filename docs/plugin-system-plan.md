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

Starlark is sandboxed - no filesystem/network access by default. We expose these built-ins:

### Core API

```python
# Git operations (read-only, safe)
git_show(path, ref="HEAD")     # Read file content from git history
git_grep(pattern, ref="HEAD")  # Search git history, returns [(file, line, content), ...]

# Working directory (read-only)
file_exists(path)              # Check if file exists in working dir
read_file(path)                # Read file from working dir (or None if missing)
list_dir(path)                 # List directory contents

# Utility
regex_match(pattern, text)     # Returns {"groups": {...}} or None
regex_find_all(pattern, text)  # Returns [{"groups": {...}}, ...]
path_join(*parts)              # Join path components
path_basename(path)            # Get filename from path
path_dirname(path)             # Get directory from path
path_ext(path)                 # Get extension (e.g., ".c")

# Logging (for debugging)
log(message)                   # Print to verbose output
```

### Go Implementation

```go
// src/boil/planners/starlark_builtins.go
package planners

import (
    "fmt"
    "os"
    "os/exec"
    "path/filepath"
    "regexp"
    "strings"

    "go.starlark.net/starlark"
    "go.starlark.net/starlarkstruct"
)

// MakeBuiltins creates the predeclared built-in functions for Starlark planners
func MakeBuiltins(gitRef string) starlark.StringDict {
    return starlark.StringDict{
        "git_show":       starlark.NewBuiltin("git_show", gitShowBuiltin(gitRef)),
        "git_grep":       starlark.NewBuiltin("git_grep", gitGrepBuiltin(gitRef)),
        "file_exists":    starlark.NewBuiltin("file_exists", fileExistsBuiltin),
        "read_file":      starlark.NewBuiltin("read_file", readFileBuiltin),
        "list_dir":       starlark.NewBuiltin("list_dir", listDirBuiltin),
        "regex_match":    starlark.NewBuiltin("regex_match", regexMatchBuiltin),
        "regex_find_all": starlark.NewBuiltin("regex_find_all", regexFindAllBuiltin),
        "path_join":      starlark.NewBuiltin("path_join", pathJoinBuiltin),
        "path_basename":  starlark.NewBuiltin("path_basename", pathBasenameBuiltin),
        "path_dirname":   starlark.NewBuiltin("path_dirname", pathDirnameBuiltin),
        "path_ext":       starlark.NewBuiltin("path_ext", pathExtBuiltin),
        "log":            starlark.NewBuiltin("log", logBuiltin),
    }
}

// git_show(path, ref="HEAD") -> str or None
func gitShowBuiltin(defaultRef string) func(*starlark.Thread, *starlark.Builtin, starlark.Tuple, []starlark.Tuple) (starlark.Value, error) {
    return func(thread *starlark.Thread, b *starlark.Builtin, args starlark.Tuple, kwargs []starlark.Tuple) (starlark.Value, error) {
        var path string
        ref := defaultRef
        if err := starlark.UnpackArgs(b.Name(), args, kwargs, "path", &path, "ref?", &ref); err != nil {
            return nil, err
        }

        cmd := exec.Command("git", "show", fmt.Sprintf("%s:%s", ref, path))
        output, err := cmd.Output()
        if err != nil {
            return starlark.None, nil // File not found in git
        }
        return starlark.String(output), nil
    }
}

// git_grep(pattern, ref="HEAD") -> [(file, line_num, content), ...]
func gitGrepBuiltin(defaultRef string) func(*starlark.Thread, *starlark.Builtin, starlark.Tuple, []starlark.Tuple) (starlark.Value, error) {
    return func(thread *starlark.Thread, b *starlark.Builtin, args starlark.Tuple, kwargs []starlark.Tuple) (starlark.Value, error) {
        var pattern string
        ref := defaultRef
        if err := starlark.UnpackArgs(b.Name(), args, kwargs, "pattern", &pattern, "ref?", &ref); err != nil {
            return nil, err
        }

        cmd := exec.Command("git", "grep", "-n", pattern, ref)
        output, _ := cmd.Output() // Ignore error (no matches = empty)

        var results []starlark.Value
        for _, line := range strings.Split(string(output), "\n") {
            if line == "" {
                continue
            }
            // Format: ref:file:linenum:content
            parts := strings.SplitN(line, ":", 4)
            if len(parts) >= 4 {
                lineNum, _ := strconv.Atoi(parts[2])
                results = append(results, starlark.Tuple{
                    starlark.String(parts[1]),        // file
                    starlark.MakeInt(lineNum),        // line_num
                    starlark.String(parts[3]),        // content
                })
            }
        }
        return starlark.NewList(results), nil
    }
}

// file_exists(path) -> bool
func fileExistsBuiltin(thread *starlark.Thread, b *starlark.Builtin, args starlark.Tuple, kwargs []starlark.Tuple) (starlark.Value, error) {
    var path string
    if err := starlark.UnpackArgs(b.Name(), args, kwargs, "path", &path); err != nil {
        return nil, err
    }
    _, err := os.Stat(path)
    return starlark.Bool(err == nil), nil
}

// read_file(path) -> str or None
func readFileBuiltin(thread *starlark.Thread, b *starlark.Builtin, args starlark.Tuple, kwargs []starlark.Tuple) (starlark.Value, error) {
    var path string
    if err := starlark.UnpackArgs(b.Name(), args, kwargs, "path", &path); err != nil {
        return nil, err
    }
    content, err := os.ReadFile(path)
    if err != nil {
        return starlark.None, nil
    }
    return starlark.String(content), nil
}

// regex_match(pattern, text) -> {"groups": {...}} or None
func regexMatchBuiltin(thread *starlark.Thread, b *starlark.Builtin, args starlark.Tuple, kwargs []starlark.Tuple) (starlark.Value, error) {
    var pattern, text string
    if err := starlark.UnpackArgs(b.Name(), args, kwargs, "pattern", &pattern, "text", &text); err != nil {
        return nil, err
    }

    re, err := regexp.Compile(pattern)
    if err != nil {
        return nil, fmt.Errorf("invalid regex: %v", err)
    }

    match := re.FindStringSubmatch(text)
    if match == nil {
        return starlark.None, nil
    }

    // Build groups dict from named captures
    groups := starlark.NewDict(len(re.SubexpNames()))
    for i, name := range re.SubexpNames() {
        if name != "" && i < len(match) {
            groups.SetKey(starlark.String(name), starlark.String(match[i]))
        }
    }

    return starlarkstruct.FromStringDict(starlark.String("match"), starlark.StringDict{
        "groups": groups,
        "full":   starlark.String(match[0]),
    }), nil
}
```

### Example: Complex Planner in Starlark

```python
# .boil/plugins/planners/linker_symbols.star
# Handles linker undefined symbol errors by finding which deleted file defines them

def name():
    return "LinkerSymbolsPlugin"

def can_handle(clue_type):
    return clue_type == "linker_undefined_symbols"

def plan(clues, git_state):
    # Collect all undefined symbols
    symbols = []
    for clue in clues:
        if clue["clue_type"] == "linker_undefined_symbols":
            sym = clue["context"].get("symbol", "")
            if sym:
                symbols.append(sym)

    if not symbols:
        return []

    # Score each deleted .c file by how many symbols it defines
    scores = []
    for deleted in git_state["deleted_files"]:
        if not deleted.endswith(".c"):
            continue

        content = git_show(deleted, git_state["ref"])
        if not content:
            continue

        score = 0
        for sym in symbols:
            if contains_definition(content, sym):
                score += 1

        if score > 0:
            scores.append({"file": deleted, "score": score})

    if not scores:
        return []

    # Sort by score descending, restore highest
    scores = sorted(scores, key=lambda x: -x["score"])
    best = scores[0]

    return [{
        "plan_type": "restore_file",
        "priority": 0,
        "target_file": best["file"],
        "action": "restore_full",
        "params": {"ref": git_state["ref"]},
        "reason": "Restore %s (defines %d symbols)" % (best["file"], best["score"]),
    }]

def contains_definition(content, symbol):
    """Check if content contains a function/variable definition for symbol."""
    # Simple heuristic: symbol followed by ( and later {
    pattern = symbol + r"\s*\([^)]*\)\s*\{"
    return regex_match(pattern, content) != None
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

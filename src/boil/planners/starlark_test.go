// Tests for Starlark planner plugins
package planners

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/mdonahoe/boiler/src/boil/pipeline"
)

// TestLoadPlannerPlugins_NoDirectory tests that missing plugins dir is not an error
func TestLoadPlannerPlugins_NoDirectory(t *testing.T) {
	origDir, _ := os.Getwd()
	tmpDir := t.TempDir()
	os.Chdir(tmpDir)
	defer os.Chdir(origDir)

	planners, err := LoadPlannerPlugins("HEAD")
	if err != nil {
		t.Fatalf("LoadPlannerPlugins() returned error: %v", err)
	}
	if len(planners) != 0 {
		t.Errorf("Expected 0 planners, got %d", len(planners))
	}
}

// TestLoadPlannerFromStarlark_ValidPlugin tests loading a valid Starlark plugin
func TestLoadPlannerFromStarlark_ValidPlugin(t *testing.T) {
	origDir, _ := os.Getwd()
	tmpDir := t.TempDir()
	os.Chdir(tmpDir)
	defer os.Chdir(origDir)

	// Create plugins directory
	pluginsDir := filepath.Join(".boil", "plugins", "planners")
	if err := os.MkdirAll(pluginsDir, 0755); err != nil {
		t.Fatalf("Failed to create plugins dir: %v", err)
	}

	// Write a valid Starlark planner
	starlarkCode := `
def name():
    return "TestStarlarkPlanner"

def can_handle(clue_type):
    return clue_type == "test_error"

def plan(clues, git_state):
    plans = []
    for clue in clues:
        if clue["clue_type"] == "test_error":
            plans.append({
                "plan_type": "restore_file",
                "priority": 10,
                "target_file": "test.txt",
                "action": "restore_full",
                "params": {"ref": git_state["ref"]},
                "reason": "Fix test error",
            })
    return plans
`
	pluginPath := filepath.Join(pluginsDir, "test_planner.star")
	if err := os.WriteFile(pluginPath, []byte(starlarkCode), 0644); err != nil {
		t.Fatalf("Failed to write plugin file: %v", err)
	}

	// Load the planner
	planner, err := LoadPlannerFromStarlark(pluginPath, "HEAD")
	if err != nil {
		t.Fatalf("LoadPlannerFromStarlark() returned error: %v", err)
	}

	// Test name
	if planner.Name() != "TestStarlarkPlanner" {
		t.Errorf("Expected name 'TestStarlarkPlanner', got %q", planner.Name())
	}

	// Test can_handle
	if !planner.CanHandle("test_error") {
		t.Error("Expected CanHandle('test_error') to return true")
	}
	if planner.CanHandle("other_error") {
		t.Error("Expected CanHandle('other_error') to return false")
	}

	// Test plan
	clues := []*pipeline.ErrorClue{
		{
			ClueType:   "test_error",
			Confidence: 1.0,
			Context:    map[string]string{"message": "test"},
			SourceLine: "test error occurred",
		},
	}
	gitState := &pipeline.GitState{
		Ref:          "HEAD",
		DeletedFiles: []string{"test.txt"},
		GitToplevel:  tmpDir,
	}

	plans, err := planner.Plan(clues, gitState)
	if err != nil {
		t.Fatalf("Plan() returned error: %v", err)
	}

	if len(plans) != 1 {
		t.Fatalf("Expected 1 plan, got %d", len(plans))
	}

	if plans[0].TargetFile != "test.txt" {
		t.Errorf("Expected target_file 'test.txt', got %q", plans[0].TargetFile)
	}
	if plans[0].Priority != 10 {
		t.Errorf("Expected priority 10, got %d", plans[0].Priority)
	}
}

// TestLoadPlannerFromStarlark_MissingFunction tests error when required function is missing
func TestLoadPlannerFromStarlark_MissingFunction(t *testing.T) {
	tmpDir := t.TempDir()

	// Missing name() function
	starlarkCode := `
def can_handle(clue_type):
    return True

def plan(clues, git_state):
    return []
`
	pluginPath := filepath.Join(tmpDir, "missing_name.star")
	if err := os.WriteFile(pluginPath, []byte(starlarkCode), 0644); err != nil {
		t.Fatalf("Failed to write plugin file: %v", err)
	}

	_, err := LoadPlannerFromStarlark(pluginPath, "HEAD")
	if err == nil {
		t.Error("Expected error for missing name() function")
	}
}

// TestStarlarkBuiltins_PathFunctions tests path utility functions
func TestStarlarkBuiltins_PathFunctions(t *testing.T) {
	tmpDir := t.TempDir()

	starlarkCode := `
def name():
    return "PathTester"

def can_handle(clue_type):
    return clue_type == "path_test"

def plan(clues, git_state):
    # Test path functions
    joined = path_join("foo", "bar", "baz.txt")
    base = path_basename("/some/path/file.txt")
    dir = path_dirname("/some/path/file.txt")
    ext = path_ext("file.tar.gz")

    return [{
        "plan_type": "test",
        "priority": 0,
        "target_file": joined,
        "action": "test",
        "params": {"base": base, "dir": dir, "ext": ext},
        "reason": "test",
    }]
`
	pluginPath := filepath.Join(tmpDir, "path_test.star")
	if err := os.WriteFile(pluginPath, []byte(starlarkCode), 0644); err != nil {
		t.Fatalf("Failed to write plugin file: %v", err)
	}

	planner, err := LoadPlannerFromStarlark(pluginPath, "HEAD")
	if err != nil {
		t.Fatalf("LoadPlannerFromStarlark() returned error: %v", err)
	}

	clues := []*pipeline.ErrorClue{{ClueType: "path_test", Confidence: 1.0, Context: map[string]string{}}}
	gitState := &pipeline.GitState{Ref: "HEAD"}

	plans, err := planner.Plan(clues, gitState)
	if err != nil {
		t.Fatalf("Plan() returned error: %v", err)
	}

	if len(plans) != 1 {
		t.Fatalf("Expected 1 plan, got %d", len(plans))
	}

	// Check path_join result
	expectedJoined := filepath.Join("foo", "bar", "baz.txt")
	if plans[0].TargetFile != expectedJoined {
		t.Errorf("path_join: expected %q, got %q", expectedJoined, plans[0].TargetFile)
	}

	// Check path_basename
	if plans[0].Params["base"] != "file.txt" {
		t.Errorf("path_basename: expected 'file.txt', got %q", plans[0].Params["base"])
	}

	// Check path_dirname
	expectedDir := "/some/path"
	if plans[0].Params["dir"] != expectedDir {
		t.Errorf("path_dirname: expected %q, got %q", expectedDir, plans[0].Params["dir"])
	}

	// Check path_ext
	if plans[0].Params["ext"] != ".gz" {
		t.Errorf("path_ext: expected '.gz', got %q", plans[0].Params["ext"])
	}
}

// TestStarlarkBuiltins_FileExists tests file_exists function
func TestStarlarkBuiltins_FileExists(t *testing.T) {
	origDir, _ := os.Getwd()
	tmpDir := t.TempDir()
	os.Chdir(tmpDir)
	defer os.Chdir(origDir)

	// Create a test file
	if err := os.WriteFile("exists.txt", []byte("hello"), 0644); err != nil {
		t.Fatalf("Failed to create test file: %v", err)
	}

	starlarkCode := `
def name():
    return "FileExistsTester"

def can_handle(clue_type):
    return clue_type == "file_test"

def plan(clues, git_state):
    exists = file_exists("exists.txt")
    not_exists = file_exists("not_exists.txt")

    result = "both_correct" if exists and not not_exists else "wrong"

    return [{
        "plan_type": "test",
        "priority": 0,
        "target_file": result,
        "action": "test",
        "params": {},
        "reason": "test",
    }]
`
	pluginPath := filepath.Join(tmpDir, "file_test.star")
	if err := os.WriteFile(pluginPath, []byte(starlarkCode), 0644); err != nil {
		t.Fatalf("Failed to write plugin file: %v", err)
	}

	planner, err := LoadPlannerFromStarlark(pluginPath, "HEAD")
	if err != nil {
		t.Fatalf("LoadPlannerFromStarlark() returned error: %v", err)
	}

	clues := []*pipeline.ErrorClue{{ClueType: "file_test", Confidence: 1.0, Context: map[string]string{}}}
	gitState := &pipeline.GitState{Ref: "HEAD"}

	plans, err := planner.Plan(clues, gitState)
	if err != nil {
		t.Fatalf("Plan() returned error: %v", err)
	}

	if len(plans) != 1 {
		t.Fatalf("Expected 1 plan, got %d", len(plans))
	}

	if plans[0].TargetFile != "both_correct" {
		t.Errorf("file_exists test failed: got %q", plans[0].TargetFile)
	}
}

// TestStarlarkBuiltins_RegexMatch tests regex_match function
func TestStarlarkBuiltins_RegexMatch(t *testing.T) {
	tmpDir := t.TempDir()

	starlarkCode := `
def name():
    return "RegexTester"

def can_handle(clue_type):
    return clue_type == "regex_test"

def plan(clues, git_state):
    match = regex_match(r"error: (?P<msg>.+)", "error: something failed")

    if match == None:
        return [{"plan_type": "test", "priority": 0, "target_file": "no_match", "action": "test", "params": {}, "reason": ""}]

    msg = ""
    groups = match["groups"]
    if "msg" in groups:
        msg = groups["msg"]

    return [{
        "plan_type": "test",
        "priority": 0,
        "target_file": msg,
        "action": "test",
        "params": {},
        "reason": "",
    }]
`
	pluginPath := filepath.Join(tmpDir, "regex_test.star")
	if err := os.WriteFile(pluginPath, []byte(starlarkCode), 0644); err != nil {
		t.Fatalf("Failed to write plugin file: %v", err)
	}

	planner, err := LoadPlannerFromStarlark(pluginPath, "HEAD")
	if err != nil {
		t.Fatalf("LoadPlannerFromStarlark() returned error: %v", err)
	}

	clues := []*pipeline.ErrorClue{{ClueType: "regex_test", Confidence: 1.0, Context: map[string]string{}}}
	gitState := &pipeline.GitState{Ref: "HEAD"}

	plans, err := planner.Plan(clues, gitState)
	if err != nil {
		t.Fatalf("Plan() returned error: %v", err)
	}

	if len(plans) != 1 {
		t.Fatalf("Expected 1 plan, got %d", len(plans))
	}

	if plans[0].TargetFile != "something failed" {
		t.Errorf("regex_match: expected 'something failed', got %q", plans[0].TargetFile)
	}
}

// TestLoadPlannerPlugins_SkipsUnderscore tests that files starting with _ are skipped
func TestLoadPlannerPlugins_SkipsUnderscore(t *testing.T) {
	origDir, _ := os.Getwd()
	tmpDir := t.TempDir()
	os.Chdir(tmpDir)
	defer os.Chdir(origDir)

	pluginsDir := filepath.Join(".boil", "plugins", "planners")
	if err := os.MkdirAll(pluginsDir, 0755); err != nil {
		t.Fatalf("Failed to create plugins dir: %v", err)
	}

	// Write a disabled plugin
	starlarkCode := `def name(): return "Disabled"`
	if err := os.WriteFile(filepath.Join(pluginsDir, "_disabled.star"), []byte(starlarkCode), 0644); err != nil {
		t.Fatalf("Failed to write plugin file: %v", err)
	}

	planners, err := LoadPlannerPlugins("HEAD")
	if err != nil {
		t.Fatalf("LoadPlannerPlugins() returned error: %v", err)
	}

	if len(planners) != 0 {
		t.Errorf("Expected 0 planners (disabled), got %d", len(planners))
	}
}

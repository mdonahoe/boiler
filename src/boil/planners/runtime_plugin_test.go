// Tests demonstrating runtime plugin loading to solve problems built-in planners cannot handle
package planners

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/mdonahoe/boiler/src/boil/pipeline"
)

// TestRuntimePlugin_SolvesUnhandledClueType demonstrates that a plugin introduced
// at runtime can handle a clue type that no built-in planner supports.
//
// Scenario:
// 1. We have a custom error clue type "custom_project_error" that built-in planners don't handle
// 2. We introduce a plugin at runtime that handles this clue type
// 3. The plugin successfully generates repair plans
func TestRuntimePlugin_SolvesUnhandledClueType(t *testing.T) {
	origDir, _ := os.Getwd()
	tmpDir := t.TempDir()
	os.Chdir(tmpDir)
	defer os.Chdir(origDir)

	// Create a fresh registry for this test
	registry := pipeline.NewPlannerRegistry()

	// Register built-in planners (none handle "custom_project_error")
	registry.Register(NewMissingFilePlanner())
	registry.Register(NewMissingDirectoryPlanner())

	// Create a clue with a custom type that no built-in planner handles
	clues := []*pipeline.ErrorClue{
		{
			ClueType:   "custom_project_error",
			Confidence: 1.0,
			Context: map[string]string{
				"file":    "config/settings.json",
				"message": "missing required configuration",
			},
			SourceLine: "error: config/settings.json: missing required configuration",
		},
	}

	gitState := &pipeline.GitState{
		Ref:          "HEAD",
		DeletedFiles: []string{"config/settings.json"},
		GitToplevel:  tmpDir,
	}

	// Verify built-in planners cannot handle this clue type
	builtInPlans, _ := registry.PlanAll(clues, gitState)
	if len(builtInPlans) > 0 {
		t.Fatalf("Expected built-in planners to produce 0 plans for custom_project_error, got %d", len(builtInPlans))
	}

	// Now introduce a plugin at runtime that handles this clue type
	pluginsDir := filepath.Join(".boil", "plugins", "planners")
	if err := os.MkdirAll(pluginsDir, 0755); err != nil {
		t.Fatalf("Failed to create plugins dir: %v", err)
	}

	// Write the plugin that handles our custom error type
	pluginCode := `
def name():
    return "CustomProjectErrorPlanner"

def can_handle(clue_type):
    return clue_type == "custom_project_error"

def plan(clues, git_state):
    plans = []
    for clue in clues:
        if clue["clue_type"] != "custom_project_error":
            continue

        file_path = clue["context"].get("file", "")
        if not file_path:
            continue

        # Check if file was deleted
        if file_path in git_state["deleted_files"]:
            plans.append({
                "plan_type": "restore_file",
                "priority": 0,
                "target_file": file_path,
                "action": "restore_full",
                "params": {"ref": git_state["ref"]},
                "reason": "Restore " + file_path + " for custom project error",
            })
    return plans
`
	pluginPath := filepath.Join(pluginsDir, "custom_error.star")
	if err := os.WriteFile(pluginPath, []byte(pluginCode), 0644); err != nil {
		t.Fatalf("Failed to write plugin file: %v", err)
	}

	// Load and register the plugin at runtime
	plugin, err := LoadPlannerFromStarlark(pluginPath, "HEAD")
	if err != nil {
		t.Fatalf("Failed to load plugin: %v", err)
	}
	registry.Register(plugin)

	// Now the registry should be able to handle the custom clue type
	plansWithPlugin, err := registry.PlanAll(clues, gitState)
	if err != nil {
		t.Fatalf("PlanAll returned error: %v", err)
	}

	if len(plansWithPlugin) != 1 {
		t.Fatalf("Expected plugin to produce 1 plan, got %d", len(plansWithPlugin))
	}

	plan := plansWithPlugin[0]
	if plan.TargetFile != "config/settings.json" {
		t.Errorf("Expected target file 'config/settings.json', got %q", plan.TargetFile)
	}
	if plan.Action != "restore_full" {
		t.Errorf("Expected action 'restore_full', got %q", plan.Action)
	}
}

// TestRuntimePlugin_HigherPriorityOverridesBuiltIn demonstrates that a plugin
// can override built-in planner behavior by using a higher priority (lower number).
func TestRuntimePlugin_HigherPriorityOverridesBuiltIn(t *testing.T) {
	origDir, _ := os.Getwd()
	tmpDir := t.TempDir()
	os.Chdir(tmpDir)
	defer os.Chdir(origDir)

	registry := pipeline.NewPlannerRegistry()

	// Register built-in MissingFilePlanner (handles "missing_file" clue type)
	registry.Register(NewMissingFilePlanner())

	clues := []*pipeline.ErrorClue{
		{
			ClueType:   "missing_file",
			Confidence: 1.0,
			Context:    map[string]string{"file_path": "special/important.h"},
			SourceLine: "fatal error: special/important.h: No such file or directory",
		},
	}

	gitState := &pipeline.GitState{
		Ref:          "HEAD",
		DeletedFiles: []string{"lib/include/special/important.h"}, // Actual path differs
		GitToplevel:  tmpDir,
	}

	// Built-in planner will try to restore "special/important.h" which doesn't exist in git
	builtInPlans, _ := registry.PlanAll(clues, gitState)

	// Now add a plugin with higher priority that resolves include paths
	pluginsDir := filepath.Join(".boil", "plugins", "planners")
	os.MkdirAll(pluginsDir, 0755)

	pluginCode := `
def name():
    return "IncludePathResolverPlanner"

def can_handle(clue_type):
    return clue_type == "missing_file"

def plan(clues, git_state):
    plans = []
    for clue in clues:
        if clue["clue_type"] != "missing_file":
            continue

        missing_path = clue["context"].get("file_path", "")
        if not missing_path:
            continue

        # Search deleted files for a match
        for deleted_file in git_state["deleted_files"]:
            if deleted_file.endswith(missing_path) or deleted_file.endswith("/" + missing_path):
                plans.append({
                    "plan_type": "restore_file",
                    "priority": -10,  # Higher priority than built-in (0)
                    "target_file": deleted_file,
                    "action": "restore_full",
                    "params": {"ref": git_state["ref"]},
                    "reason": "Restore " + deleted_file + " (resolved from include: " + missing_path + ")",
                })
                break
    return plans
`
	pluginPath := filepath.Join(pluginsDir, "include_resolver.star")
	os.WriteFile(pluginPath, []byte(pluginCode), 0644)

	plugin, err := LoadPlannerFromStarlark(pluginPath, "HEAD")
	if err != nil {
		t.Fatalf("Failed to load plugin: %v", err)
	}
	registry.Register(plugin)

	// Now get plans - plugin's higher priority plan should come first
	plansWithPlugin, _ := registry.PlanAll(clues, gitState)

	if len(plansWithPlugin) < 1 {
		t.Fatalf("Expected at least 1 plan, got %d", len(plansWithPlugin))
	}

	// The first plan (highest priority) should be from the plugin
	firstPlan := plansWithPlugin[0]
	if firstPlan.Priority != -10 {
		t.Errorf("Expected first plan to have priority -10 (from plugin), got %d", firstPlan.Priority)
	}
	if firstPlan.TargetFile != "lib/include/special/important.h" {
		t.Errorf("Expected plugin to resolve to 'lib/include/special/important.h', got %q", firstPlan.TargetFile)
	}

	// Verify built-in planner also generated a plan (but lower priority)
	if len(builtInPlans) > 0 && len(plansWithPlugin) > 1 {
		// Built-in plan should have priority 0 (lower priority = later in sorted list)
		for _, p := range plansWithPlugin[1:] {
			if p.Priority == 0 {
				t.Logf("Built-in planner also generated plan with priority 0 (as expected)")
				break
			}
		}
	}
}

// TestRuntimePlugin_UsesGitStateDeletedFiles demonstrates that plugins can
// access git_state["deleted_files"] to find files that need restoration.
func TestRuntimePlugin_UsesGitStateDeletedFiles(t *testing.T) {
	origDir, _ := os.Getwd()
	tmpDir := t.TempDir()
	os.Chdir(tmpDir)
	defer os.Chdir(origDir)

	pluginsDir := filepath.Join(".boil", "plugins", "planners")
	os.MkdirAll(pluginsDir, 0755)

	// Plugin that restores all deleted files mentioned in clues
	pluginCode := `
def name():
    return "DeletedFileRestorerPlanner"

def can_handle(clue_type):
    return clue_type == "file_reference_error"

def plan(clues, git_state):
    plans = []
    restored = set()

    for clue in clues:
        if clue["clue_type"] != "file_reference_error":
            continue

        ref_file = clue["context"].get("referenced_file", "")
        if not ref_file or ref_file in restored:
            continue

        # Check if this file is in the deleted files list
        for deleted in git_state["deleted_files"]:
            if deleted == ref_file or deleted.endswith("/" + ref_file):
                restored.add(ref_file)
                plans.append({
                    "plan_type": "restore_file",
                    "priority": 0,
                    "target_file": deleted,
                    "action": "restore_full",
                    "params": {"ref": git_state["ref"]},
                    "reason": "Restore deleted file: " + deleted,
                })
                break

    return plans
`
	pluginPath := filepath.Join(pluginsDir, "deleted_restorer.star")
	os.WriteFile(pluginPath, []byte(pluginCode), 0644)

	plugin, err := LoadPlannerFromStarlark(pluginPath, "HEAD")
	if err != nil {
		t.Fatalf("Failed to load plugin: %v", err)
	}

	clues := []*pipeline.ErrorClue{
		{
			ClueType:   "file_reference_error",
			Confidence: 1.0,
			Context:    map[string]string{"referenced_file": "utils.c"},
			SourceLine: "error: utils.c not found",
		},
		{
			ClueType:   "file_reference_error",
			Confidence: 1.0,
			Context:    map[string]string{"referenced_file": "config.h"},
			SourceLine: "error: config.h not found",
		},
	}

	gitState := &pipeline.GitState{
		Ref:          "HEAD",
		DeletedFiles: []string{"src/utils.c", "include/config.h", "other/unrelated.txt"},
		GitToplevel:  tmpDir,
	}

	plans, err := plugin.Plan(clues, gitState)
	if err != nil {
		t.Fatalf("Plan returned error: %v", err)
	}

	if len(plans) != 2 {
		t.Fatalf("Expected 2 plans (one for each referenced file), got %d", len(plans))
	}

	// Verify the correct files were matched
	targetFiles := make(map[string]bool)
	for _, p := range plans {
		targetFiles[p.TargetFile] = true
	}

	if !targetFiles["src/utils.c"] {
		t.Error("Expected plan for 'src/utils.c'")
	}
	if !targetFiles["include/config.h"] {
		t.Error("Expected plan for 'include/config.h'")
	}
}

// TestRuntimePlugin_MultiplePluginsCooperate demonstrates that multiple plugins
// can be loaded and work together to handle different aspects of errors.
func TestRuntimePlugin_MultiplePluginsCooperate(t *testing.T) {
	origDir, _ := os.Getwd()
	tmpDir := t.TempDir()
	os.Chdir(tmpDir)
	defer os.Chdir(origDir)

	registry := pipeline.NewPlannerRegistry()
	pluginsDir := filepath.Join(".boil", "plugins", "planners")
	os.MkdirAll(pluginsDir, 0755)

	// First plugin: handles type errors
	typePlugin := `
def name():
    return "TypeErrorPlanner"

def can_handle(clue_type):
    return clue_type == "type_error"

def plan(clues, git_state):
    plans = []
    for clue in clues:
        if clue["clue_type"] == "type_error":
            plans.append({
                "plan_type": "restore_file",
                "priority": 0,
                "target_file": clue["context"].get("file", "unknown"),
                "action": "restore_full",
                "params": {"ref": git_state["ref"]},
                "reason": "Fix type error",
            })
    return plans
`
	os.WriteFile(filepath.Join(pluginsDir, "type_error.star"), []byte(typePlugin), 0644)

	// Second plugin: handles linker errors
	linkerPlugin := `
def name():
    return "LinkerErrorPlanner"

def can_handle(clue_type):
    return clue_type == "linker_error"

def plan(clues, git_state):
    plans = []
    for clue in clues:
        if clue["clue_type"] == "linker_error":
            plans.append({
                "plan_type": "restore_file",
                "priority": 5,
                "target_file": clue["context"].get("object_file", "unknown"),
                "action": "restore_full",
                "params": {"ref": git_state["ref"]},
                "reason": "Fix linker error",
            })
    return plans
`
	os.WriteFile(filepath.Join(pluginsDir, "linker_error.star"), []byte(linkerPlugin), 0644)

	// Load both plugins
	plugins, err := LoadPlannerPlugins("HEAD")
	if err != nil {
		t.Fatalf("Failed to load plugins: %v", err)
	}

	if len(plugins) != 2 {
		t.Fatalf("Expected 2 plugins, got %d", len(plugins))
	}

	for _, p := range plugins {
		registry.Register(p)
	}

	// Create clues that each plugin handles
	clues := []*pipeline.ErrorClue{
		{
			ClueType:   "type_error",
			Confidence: 1.0,
			Context:    map[string]string{"file": "types.h"},
			SourceLine: "error: unknown type",
		},
		{
			ClueType:   "linker_error",
			Confidence: 1.0,
			Context:    map[string]string{"object_file": "utils.o"},
			SourceLine: "undefined reference to 'func'",
		},
	}

	gitState := &pipeline.GitState{
		Ref:          "HEAD",
		DeletedFiles: []string{"types.h", "utils.o"},
		GitToplevel:  tmpDir,
	}

	plans, _ := registry.PlanAll(clues, gitState)

	if len(plans) != 2 {
		t.Fatalf("Expected 2 plans from cooperating plugins, got %d", len(plans))
	}

	// Verify both plugins contributed
	hasTypePlan := false
	hasLinkerPlan := false
	for _, p := range plans {
		if p.TargetFile == "types.h" {
			hasTypePlan = true
		}
		if p.TargetFile == "utils.o" {
			hasLinkerPlan = true
		}
	}

	if !hasTypePlan {
		t.Error("Expected TypeErrorPlanner to generate a plan")
	}
	if !hasLinkerPlan {
		t.Error("Expected LinkerErrorPlanner to generate a plan")
	}
}

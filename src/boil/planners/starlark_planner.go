// StarlarkPlanner implements pipeline.Planner using Starlark scripts
package planners

import (
	"fmt"
	"os"
	"path/filepath"
	"sort"

	"github.com/mdonahoe/boiler/src/boil/pipeline"
	"go.starlark.net/starlark"
)

// StarlarkPlanner wraps a Starlark script that implements the Planner interface
type StarlarkPlanner struct {
	name      string
	filePath  string
	thread    *starlark.Thread
	globals   starlark.StringDict
	canHandle *starlark.Function
	planFunc  *starlark.Function
}

// LoadPlannerFromStarlark loads a planner from a .star file
func LoadPlannerFromStarlark(filePath string, gitRef string) (*StarlarkPlanner, error) {
	// Read the file
	data, err := os.ReadFile(filePath)
	if err != nil {
		return nil, fmt.Errorf("failed to read %s: %w", filePath, err)
	}

	// Create thread and builtins
	thread := &starlark.Thread{Name: filepath.Base(filePath)}
	builtins := MakeBuiltins(gitRef)

	// Execute the script
	globals, err := starlark.ExecFile(thread, filePath, data, builtins)
	if err != nil {
		return nil, fmt.Errorf("failed to execute %s: %w", filePath, err)
	}

	// Extract required functions
	nameFunc, ok := globals["name"]
	if !ok {
		return nil, fmt.Errorf("%s: missing required function 'name'", filePath)
	}
	nameFn, ok := nameFunc.(*starlark.Function)
	if !ok {
		return nil, fmt.Errorf("%s: 'name' is not a function", filePath)
	}

	canHandleFunc, ok := globals["can_handle"]
	if !ok {
		return nil, fmt.Errorf("%s: missing required function 'can_handle'", filePath)
	}
	canHandleFn, ok := canHandleFunc.(*starlark.Function)
	if !ok {
		return nil, fmt.Errorf("%s: 'can_handle' is not a function", filePath)
	}

	planFunc, ok := globals["plan"]
	if !ok {
		return nil, fmt.Errorf("%s: missing required function 'plan'", filePath)
	}
	planFn, ok := planFunc.(*starlark.Function)
	if !ok {
		return nil, fmt.Errorf("%s: 'plan' is not a function", filePath)
	}

	// Call name() to get the planner name
	nameVal, err := starlark.Call(thread, nameFn, nil, nil)
	if err != nil {
		return nil, fmt.Errorf("%s: error calling name(): %w", filePath, err)
	}
	nameStr, ok := starlark.AsString(nameVal)
	if !ok {
		return nil, fmt.Errorf("%s: name() did not return a string", filePath)
	}

	return &StarlarkPlanner{
		name:      nameStr,
		filePath:  filePath,
		thread:    thread,
		globals:   globals,
		canHandle: canHandleFn,
		planFunc:  planFn,
	}, nil
}

// Name returns the planner name
func (p *StarlarkPlanner) Name() string {
	return p.name
}

// CanHandle checks if this planner can handle a clue type
func (p *StarlarkPlanner) CanHandle(clueType string) bool {
	result, err := starlark.Call(p.thread, p.canHandle, starlark.Tuple{starlark.String(clueType)}, nil)
	if err != nil {
		if isVerbose() {
			fmt.Printf("[Plugin:%s] Error in can_handle: %v\n", p.name, err)
		}
		return false
	}

	if b, ok := result.(starlark.Bool); ok {
		return bool(b)
	}
	return false
}

// Plan generates repair plans from clues
func (p *StarlarkPlanner) Plan(clues []*pipeline.ErrorClue, gitState *pipeline.GitState) ([]*pipeline.RepairPlan, error) {
	// Convert clues to Starlark values
	starlarkClues, err := cluesToStarlark(clues)
	if err != nil {
		return nil, err
	}

	// Convert git state to Starlark dict
	starlarkGitState, err := gitStateToStarlark(gitState)
	if err != nil {
		return nil, err
	}

	// Call plan(clues, git_state)
	result, err := starlark.Call(p.thread, p.planFunc, starlark.Tuple{starlarkClues, starlarkGitState}, nil)
	if err != nil {
		return nil, fmt.Errorf("error calling plan(): %w", err)
	}

	// Convert result back to Go
	return starlarkToPlans(result, clues)
}

// cluesToStarlark converts ErrorClue slice to Starlark list
func cluesToStarlark(clues []*pipeline.ErrorClue) (*starlark.List, error) {
	var starlarkClues []starlark.Value
	for _, clue := range clues {
		context := starlark.NewDict(len(clue.Context))
		for k, v := range clue.Context {
			context.SetKey(starlark.String(k), starlark.String(v))
		}

		clueDict := starlark.NewDict(4)
		clueDict.SetKey(starlark.String("clue_type"), starlark.String(clue.ClueType))
		clueDict.SetKey(starlark.String("confidence"), starlark.Float(clue.Confidence))
		clueDict.SetKey(starlark.String("context"), context)
		clueDict.SetKey(starlark.String("source_line"), starlark.String(clue.SourceLine))
		starlarkClues = append(starlarkClues, clueDict)
	}
	return starlark.NewList(starlarkClues), nil
}

// gitStateToStarlark converts GitState to Starlark dict
func gitStateToStarlark(gitState *pipeline.GitState) (*starlark.Dict, error) {
	// Convert deleted files to list
	var deletedFiles []starlark.Value
	for _, f := range gitState.DeletedFiles {
		deletedFiles = append(deletedFiles, starlark.String(f))
	}

	// Convert partial files to list of dicts
	var partialFiles []starlark.Value
	for _, pf := range gitState.PartialFiles {
		pfDict := starlark.NewDict(3)
		pfDict.SetKey(starlark.String("file"), starlark.String(pf.File))
		pfDict.SetKey(starlark.String("line_ratio"), starlark.String(pf.LineRatio))
		pfDict.SetKey(starlark.String("status"), starlark.String(pf.Status))
		partialFiles = append(partialFiles, pfDict)
	}

	result := starlark.NewDict(4)
	result.SetKey(starlark.String("ref"), starlark.String(gitState.Ref))
	result.SetKey(starlark.String("git_toplevel"), starlark.String(gitState.GitToplevel))
	result.SetKey(starlark.String("deleted_files"), starlark.NewList(deletedFiles))
	result.SetKey(starlark.String("partial_files"), starlark.NewList(partialFiles))
	return result, nil
}

// starlarkToPlans converts Starlark list to RepairPlan slice
func starlarkToPlans(result starlark.Value, clues []*pipeline.ErrorClue) ([]*pipeline.RepairPlan, error) {
	list, ok := result.(*starlark.List)
	if !ok {
		return nil, fmt.Errorf("plan() must return a list, got %s", result.Type())
	}

	var plans []*pipeline.RepairPlan
	iter := list.Iterate()
	defer iter.Done()

	var val starlark.Value
	for iter.Next(&val) {
		dict, ok := val.(*starlark.Dict)
		if !ok {
			continue // Skip non-dict items
		}

		plan := &pipeline.RepairPlan{}

		// Extract required fields
		if v, found, _ := dict.Get(starlark.String("plan_type")); found {
			if s, ok := starlark.AsString(v); ok {
				plan.PlanType = s
			}
		}
		if v, found, _ := dict.Get(starlark.String("priority")); found {
			if i, ok := v.(starlark.Int); ok {
				priority, _ := i.Int64()
				plan.Priority = int(priority)
			}
		}
		if v, found, _ := dict.Get(starlark.String("target_file")); found {
			if s, ok := starlark.AsString(v); ok {
				plan.TargetFile = s
			}
		}
		if v, found, _ := dict.Get(starlark.String("action")); found {
			if s, ok := starlark.AsString(v); ok {
				plan.Action = s
			}
		}
		if v, found, _ := dict.Get(starlark.String("reason")); found {
			if s, ok := starlark.AsString(v); ok {
				plan.Reason = s
			}
		}

		// Extract params as map
		if v, found, _ := dict.Get(starlark.String("params")); found {
			if paramsDict, ok := v.(*starlark.Dict); ok {
				plan.Params = make(map[string]interface{})
				for _, key := range paramsDict.Keys() {
					if keyStr, ok := starlark.AsString(key); ok {
						if val, found, _ := paramsDict.Get(key); found {
							if valStr, ok := starlark.AsString(val); ok {
								plan.Params[keyStr] = valStr
							}
						}
					}
				}
			}
		}

		// Use first clue as source if not specified
		if len(clues) > 0 {
			plan.ClueSource = clues[0]
		}

		plans = append(plans, plan)
	}

	return plans, nil
}

// LoadPlannerPlugins loads Starlark planner plugins from .boil/plugins/planners/
func LoadPlannerPlugins(gitRef string) ([]*StarlarkPlanner, error) {
	pluginsDir := ".boil/plugins/planners"

	// Check if plugins directory exists
	info, err := os.Stat(pluginsDir)
	if os.IsNotExist(err) {
		return nil, nil // No plugins directory - not an error
	}
	if err != nil {
		return nil, fmt.Errorf("failed to stat plugins directory: %w", err)
	}
	if !info.IsDir() {
		return nil, fmt.Errorf("%s is not a directory", pluginsDir)
	}

	// Read directory entries
	entries, err := os.ReadDir(pluginsDir)
	if err != nil {
		return nil, fmt.Errorf("failed to read plugins directory: %w", err)
	}

	// Sort for consistent ordering
	sort.Slice(entries, func(i, j int) bool {
		return entries[i].Name() < entries[j].Name()
	})

	var planners []*StarlarkPlanner
	for _, entry := range entries {
		// Skip directories and non-.star files
		if entry.IsDir() {
			continue
		}
		ext := filepath.Ext(entry.Name())
		if ext != ".star" && ext != ".starlark" {
			continue
		}

		// Skip files starting with underscore (disabled plugins)
		if entry.Name()[0] == '_' {
			continue
		}

		filePath := filepath.Join(pluginsDir, entry.Name())
		planner, err := LoadPlannerFromStarlark(filePath, gitRef)
		if err != nil {
			if isVerbose() {
				fmt.Printf("[Plugin] Error loading %s: %v\n", entry.Name(), err)
			}
			continue
		}

		if isVerbose() {
			fmt.Printf("[Plugin] Loaded planner: %s\n", planner.Name())
		}
		planners = append(planners, planner)
	}

	return planners, nil
}

// RegisterPlannerPlugins loads and registers planner plugins from .boil/plugins/planners/
func RegisterPlannerPlugins(gitRef string) error {
	planners, err := LoadPlannerPlugins(gitRef)
	if err != nil {
		return err
	}

	for _, p := range planners {
		pipeline.RegisterPlanner(p)
	}

	return nil
}

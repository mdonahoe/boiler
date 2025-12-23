// Registration of all planners with the global registry
package planners

import (
	"github.com/mdonahoe/boiler/src/boil/pipeline"
)

// RegisterAllPlanners registers all planners with the global registry,
// including both built-in planners and plugins from .boil/plugins/planners/
func RegisterAllPlanners() error {
	// Register built-in planners
	pipeline.RegisterPlanner(NewMissingFilePlanner())
	pipeline.RegisterPlanner(NewMissingDirectoryPlanner())
	pipeline.RegisterPlanner(NewMakeNoRulePlanner())
	pipeline.RegisterPlanner(NewMakeMissingTargetPlanner())
	pipeline.RegisterPlanner(NewPermissionFixPlanner())
	pipeline.RegisterPlanner(NewPythonNameErrorPlanner())
	pipeline.RegisterPlanner(NewTestFailurePlanner())
	pipeline.RegisterPlanner(NewMissingCIncludePlanner())
	pipeline.RegisterPlanner(NewMissingCFunctionPlanner())
	pipeline.RegisterPlanner(NewUnknownTypeNamePlanner())
	pipeline.RegisterPlanner(NewLinkerUndefinedSymbolsPlanner())
	pipeline.RegisterPlanner(NewCSyntaxErrorPlanner())

	// Register planner plugins from .boil/plugins/planners/
	// Uses "HEAD" as default ref; built-ins can override with git_state["ref"]
	if err := RegisterPlannerPlugins("HEAD"); err != nil {
		return err
	}

	return nil
}

// Registration of all planners with the global registry
package planners

import (
	"github.com/mdonahoe/boiler/src/boil/pipeline"
)

// RegisterAllPlanners registers all planners with the global registry
func RegisterAllPlanners() {
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
}

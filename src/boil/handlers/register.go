// Handler registration for the boil pipeline
package handlers

import (
	"fmt"

	"github.com/mdonahoe/boiler/src/boil/detectors"
	"github.com/mdonahoe/boiler/src/boil/executors"
	"github.com/mdonahoe/boiler/src/boil/planners"
	"github.com/mdonahoe/boiler/src/boil/pipeline"
)

// RegisterAllHandlers registers all detectors, planners, and executors
func RegisterAllHandlers() error {
	// Register detectors
	if err := detectors.RegisterAllDetectors(); err != nil {
		return fmt.Errorf("failed to register detectors: %w", err)
	}

	// Register planners
	if err := planners.RegisterAllPlanners(); err != nil {
		return fmt.Errorf("failed to register planners: %w", err)
	}

	// Register executors
	executors.RegisterAllExecutors()

	// Log registration summary if verbose
	if pipeline.IsVerbose() {
		registry := pipeline.GetDetectorRegistry()
		plannerRegistry := pipeline.GetPlannerRegistry()
		executorRegistry := pipeline.GetExecutorRegistry()

		fmt.Printf("[Pipeline] Registered %d detectors\n", len(registry.ListDetectors()))
		fmt.Printf("[Pipeline] Registered %d planners\n", len(plannerRegistry.ListPlanners()))
		fmt.Printf("[Pipeline] Registered %d executors\n", len(executorRegistry.ListExecutors()))
	}

	return nil
}

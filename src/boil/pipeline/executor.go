// Executor interface and registry for Stage 3: Repair Execution
package pipeline

import (
	"fmt"
)

// Executor executes RepairPlan objects and returns RepairResult objects
type Executor interface {
	// Name returns the human-readable name of this executor
	Name() string

	// CanHandle checks if this executor can handle a specific action
	CanHandle(action string) bool

	// Execute executes a repair plan and returns the result
	Execute(plan *RepairPlan) (*RepairResult, error)

	// ValidatePlan validates that a plan is safe to execute
	// Returns (isValid, errorMessage)
	ValidatePlan(plan *RepairPlan) (bool, string)
}

// ExecutorRegistry manages all repair executors
type ExecutorRegistry struct {
	executors []Executor
}

// NewExecutorRegistry creates a new executor registry
func NewExecutorRegistry() *ExecutorRegistry {
	return &ExecutorRegistry{
		executors: make([]Executor, 0),
	}
}

// Register adds an executor to the registry
func (r *ExecutorRegistry) Register(executor Executor) {
	r.executors = append(r.executors, executor)
}

// ExecutePlans executes repair plans in order until one succeeds or all fail
func (r *ExecutorRegistry) ExecutePlans(plans []*RepairPlan) (*RepairResult, error) {
	if len(plans) == 0 {
		return &RepairResult{
			Success:        false,
			PlansAttempted: []*RepairPlan{},
			FilesModified:  []string{},
			ErrorMessage:   "No plans to execute",
		}, nil
	}

	var allAttempted []*RepairPlan
	var allModified []string

	// Check for verbose mode
	verbose := isVerbose()

	for _, plan := range plans {
		// Find executor that can handle this action
		executor := r.findExecutor(plan.Action)
		if executor == nil {
			if verbose {
				fmt.Printf("[Executor] No executor found for action: %s\n", plan.Action)
			}
			continue
		}

		// Validate plan
		isValid, errorMsg := executor.ValidatePlan(plan)
		if !isValid {
			if verbose {
				fmt.Printf("[Executor:%s] Plan validation failed: %s\n", executor.Name(), errorMsg)
			}
			continue
		}

		// Execute plan
		if verbose {
			fmt.Printf("[Executor:%s] Executing: %s on %s\n", executor.Name(), plan.Action, plan.TargetFile)
		}

		result, err := executor.Execute(plan)
		if err != nil {
			if verbose {
				fmt.Printf("[Executor:%s] Exception: %v\n", executor.Name(), err)
			}
			// Continue with next plan
			continue
		}

		allAttempted = append(allAttempted, plan)
		allModified = append(allModified, result.FilesModified...)

		if result.Success {
			// Success! Return immediately
			return &RepairResult{
				Success:        true,
				PlansAttempted: allAttempted,
				FilesModified:  allModified,
				ErrorMessage:   "",
			}, nil
		}

		if verbose {
			fmt.Printf("[Executor:%s] Failed: %s\n", executor.Name(), result.ErrorMessage)
		}
	}

	// All plans failed
	return &RepairResult{
		Success:        false,
		PlansAttempted: allAttempted,
		FilesModified:  allModified,
		ErrorMessage:   "All repair plans failed",
	}, nil
}

// findExecutor finds an executor that can handle the given action
func (r *ExecutorRegistry) findExecutor(action string) Executor {
	for _, executor := range r.executors {
		if executor.CanHandle(action) {
			return executor
		}
	}
	return nil
}

// ListExecutors returns list of registered executor names
func (r *ExecutorRegistry) ListExecutors() []string {
	names := make([]string, len(r.executors))
	for i, e := range r.executors {
		names[i] = e.Name()
	}
	return names
}

// Global registry instance
var globalExecutorRegistry = NewExecutorRegistry()

// RegisterExecutor registers an executor with the global registry
func RegisterExecutor(executor Executor) {
	globalExecutorRegistry.Register(executor)
}

// GetExecutorRegistry returns the global executor registry
func GetExecutorRegistry() *ExecutorRegistry {
	return globalExecutorRegistry
}

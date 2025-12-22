// Planner interface and registry for Stage 2: Repair Planning
package pipeline

import (
	"fmt"
	"sort"
)

// Planner converts ErrorClue objects into RepairPlan objects
type Planner interface {
	// Name returns the human-readable name of this planner
	Name() string

	// CanHandle checks if this planner can handle a specific clue type
	CanHandle(clueType string) bool

	// Plan converts ErrorClues into one or more RepairPlan objects
	// Planners receive ALL clues and should filter to the ones they care about
	Plan(clues []*ErrorClue, gitState *GitState) ([]*RepairPlan, error)
}

// PlannerRegistry manages all repair planners
type PlannerRegistry struct {
	planners []Planner
}

// NewPlannerRegistry creates a new planner registry
func NewPlannerRegistry() *PlannerRegistry {
	return &PlannerRegistry{
		planners: make([]Planner, 0),
	}
}

// Register adds a planner to the registry
func (r *PlannerRegistry) Register(planner Planner) {
	r.planners = append(r.planners, planner)
}

// PlanAll runs all planners and returns all RepairPlan objects, sorted by priority
func (r *PlannerRegistry) PlanAll(clues []*ErrorClue, gitState *GitState) ([]*RepairPlan, error) {
	var allPlans []*RepairPlan

	// Get unique clue types to determine which planners to call
	clueTypes := make(map[string]bool)
	for _, clue := range clues {
		clueTypes[clue.ClueType] = true
	}

	// Check for verbose mode
	verbose := isVerbose()

	for _, planner := range r.planners {
		// Check if this planner handles any of the clue types we have
		canHandle := false
		for clueType := range clueTypes {
			if planner.CanHandle(clueType) {
				canHandle = true
				break
			}
		}

		if !canHandle {
			continue
		}

		// Call planner
		plans, err := planner.Plan(clues, gitState)
		if err != nil {
			if verbose {
				fmt.Printf("[Planner:%s] Error planning: %v\n", planner.Name(), err)
			}
			// Continue with other planners
			continue
		}

		if len(plans) > 0 {
			if verbose {
				fmt.Printf("[Planner:%s] Generated %d plan(s)\n", planner.Name(), len(plans))
			}
			allPlans = append(allPlans, plans...)
		}
	}

	// Sort plans by priority (lower = higher priority)
	sort.Slice(allPlans, func(i, j int) bool {
		return allPlans[i].Priority < allPlans[j].Priority
	})

	return allPlans, nil
}

// ListPlanners returns list of registered planner names
func (r *PlannerRegistry) ListPlanners() []string {
	names := make([]string, len(r.planners))
	for i, p := range r.planners {
		names[i] = p.Name()
	}
	return names
}

// Global registry instance
var globalPlannerRegistry = NewPlannerRegistry()

// RegisterPlanner registers a planner with the global registry
func RegisterPlanner(planner Planner) {
	globalPlannerRegistry.Register(planner)
}

// GetPlannerRegistry returns the global planner registry
func GetPlannerRegistry() *PlannerRegistry {
	return globalPlannerRegistry
}

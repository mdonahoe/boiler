// Main pipeline orchestration for the 3-stage repair system
//
// This coordinates the flow: Detection → Planning → Execution
package pipeline

import (
	"fmt"
	"strings"
	"time"
)

// Timer tracks execution time for different pipeline stages
type Timer struct {
	prev    time.Time
	timings map[string]time.Duration
}

// NewTimer creates a new timer
func NewTimer() *Timer {
	return &Timer{
		prev:    time.Now(),
		timings: make(map[string]time.Duration),
	}
}

// Mark records the time since the last mark
func (t *Timer) Mark(name string) {
	now := time.Now()
	t.timings[name] = now.Sub(t.prev)
	t.prev = now
}

// RunPipeline runs the full 3-stage pipeline: Detection → Planning → Execution
//
// Supports multi-fix mode: after a successful plan execution, removes fixed clues
// and continues planning/executing until no clues remain or no plans succeed.
func RunPipeline(stderr, stdout string, gitState *GitState, debug, execute bool) (*RepairResult, error) {
	t := NewTimer()

	if debug {
		fmt.Println(strings.Repeat("=", 80))
		fmt.Println("PIPELINE START")
		fmt.Println(strings.Repeat("=", 80))
	}

	// Stage 1: Detection
	if debug {
		fmt.Println("\n--- STAGE 1: DETECTION ---")
	}

	detectorRegistry := GetDetectorRegistry()
	allClues, err := detectorRegistry.DetectAll(stderr, stdout)
	if err != nil {
		return nil, err
	}

	if len(allClues) == 0 {
		if debug {
			fmt.Println("No error clues detected")
		}
		return &RepairResult{
			Success:        false,
			PlansAttempted: []*RepairPlan{},
			FilesModified:  []string{},
			ErrorMessage:   "No error clues detected by any detector",
			CluesDetected:  []*ErrorClue{},
			PlansGenerated: []*RepairPlan{},
			Timings:        make(map[string]time.Duration),
		}, nil
	}

	if debug {
		fmt.Printf("\nDetected %d error clue(s):\n", len(allClues))
		for i, clue := range allClues {
			fmt.Printf("  %d. %s\n", i+1, clue.String())
		}
	}

	t.Mark("detect_clues")

	// Initialize tracking for multi-fix loop
	remainingClues := make([]*ErrorClue, len(allClues))
	copy(remainingClues, allClues)
	var allPlansGenerated []*RepairPlan
	var allPlansAttempted []*RepairPlan
	var allFilesModified []string

	plannerRegistry := GetPlannerRegistry()
	executorRegistry := GetExecutorRegistry()

	// Multi-fix loop: keep planning and executing until no clues remain
	fixRound := 0
	for len(remainingClues) > 0 {
		fixRound++
		if debug {
			fmt.Printf("\n--- FIX ROUND %d: %d clue(s) remaining ---\n", fixRound, len(remainingClues))
		}

		// Stage 2: Planning (on remaining clues)
		if debug {
			fmt.Println("\n--- STAGE 2: PLANNING ---")
		}

		plans, err := plannerRegistry.PlanAll(remainingClues, gitState)
		if err != nil {
			if debug {
				fmt.Printf("Planning error: %v\n", err)
			}
			break
		}

		// Initialize clues_fixed for each plan to contain at least the clue_source
		for _, plan := range plans {
			if plan.ClueSource == nil {
				return nil, fmt.Errorf("plan %v created without a clue", plan)
			}
			if len(plan.CluesFixed) == 0 {
				plan.CluesFixed = []*ErrorClue{plan.ClueSource}
			}
		}

		t.Mark(fmt.Sprintf("plan_round_%d", fixRound))

		if len(plans) == 0 {
			if debug {
				fmt.Println("No repair plans generated for remaining clues")
			}
			break
		}

		if debug {
			fmt.Printf("\nGenerated %d repair plan(s) (sorted by priority):\n", len(plans))
			for i, plan := range plans {
				fmt.Printf("  %d. [Priority %d] %s\n", i+1, plan.Priority, plan.String())
				fmt.Printf("      Reason: %s\n", plan.Reason)
				fmt.Printf("      Fixes %d clue(s)\n", len(plan.CluesFixed))
			}
		}

		allPlansGenerated = append(allPlansGenerated, plans...)

		// Stage 3: Execution (try plans until one succeeds)
		if !execute {
			break
		}

		if debug {
			fmt.Println("\n--- STAGE 3: EXECUTION ---")
		}

		result, err := executorRegistry.ExecutePlans(plans)
		if err != nil {
			if debug {
				fmt.Printf("Execution error: %v\n", err)
			}
			break
		}

		t.Mark(fmt.Sprintf("exec_round_%d", fixRound))

		allPlansAttempted = append(allPlansAttempted, result.PlansAttempted...)
		allFilesModified = append(allFilesModified, result.FilesModified...)

		if !result.Success {
			if debug {
				fmt.Printf("No plans succeeded in round %d, stopping\n", fixRound)
			}
			break
		}

		// Success! Remove the clues that were fixed by this plan
		if len(result.PlansAttempted) > 0 {
			successfulPlan := result.PlansAttempted[len(result.PlansAttempted)-1] // Last attempted is the successful one
			cluesToRemove := successfulPlan.CluesFixed

			if debug {
				fmt.Printf("\n[Pipeline] Plan succeeded! Removing %d fixed clue(s)\n", len(cluesToRemove))
			}

			// Remove fixed clues from remaining_clues
			newRemaining := []*ErrorClue{}
			for _, c := range remainingClues {
				found := false
				for _, toRemove := range cluesToRemove {
					if c == toRemove {
						found = true
						break
					}
				}
				if !found {
					newRemaining = append(newRemaining, c)
				}
			}
			remainingClues = newRemaining

			if debug {
				fmt.Printf("[Pipeline] %d clue(s) remaining\n", len(remainingClues))
			}
		}
	}

	// Determine overall success
	overallSuccess := len(remainingClues) < len(allClues) // Fixed at least one clue

	if debug {
		fmt.Printf("\nFixed %d / %d clue(s)\n", len(allClues)-len(remainingClues), len(allClues))
		fmt.Println(strings.Repeat("=", 80))
		fmt.Println("PIPELINE END")
		fmt.Println(strings.Repeat("=", 80))
	}

	errorMessage := ""
	if !overallSuccess {
		errorMessage = "Could not fix all clues"
	}

	return &RepairResult{
		Success:        overallSuccess,
		PlansAttempted: allPlansAttempted,
		FilesModified:  uniqueStrings(allFilesModified),
		ErrorMessage:   errorMessage,
		CluesDetected:  allClues,
		PlansGenerated: allPlansGenerated,
		Timings:        t.timings,
	}, nil
}

// HasPipelineHandlers checks if any handlers are registered in the pipeline
func HasPipelineHandlers() bool {
	detectorRegistry := GetDetectorRegistry()
	return len(detectorRegistry.ListDetectors()) > 0
}

// uniqueStrings returns a deduplicated slice of strings
func uniqueStrings(input []string) []string {
	seen := make(map[string]bool)
	result := []string{}
	for _, s := range input {
		if !seen[s] {
			seen[s] = true
			result = append(result, s)
		}
	}
	return result
}

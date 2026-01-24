// Core data models for the 3-stage repair pipeline.
//
// Stage 1: Detectors produce ErrorClue objects
// Stage 2: Planners convert ErrorClue objects into RepairPlan objects
// Stage 3: Executors execute RepairPlan objects and return RepairResult objects
package pipeline

import (
	"fmt"
	"time"
)

// ErrorClue represents evidence of a specific error type found in stderr/stdout.
// Produced by Stage 1 (Detection).
type ErrorClue struct {
	ClueType   string            // e.g., "permission_error", "missing_file", "name_error"
	Confidence float64           // 0.0-1.0, how confident we are this is the right error
	Context    map[string]string // extracted details (file_path, symbol_name, etc.)
	SourceLine string            // the actual error line that triggered this clue
}

func (e *ErrorClue) String() string {
	return fmt.Sprintf("ErrorClue(type=%s, confidence=%.2f, context=%v)", e.ClueType, e.Confidence, e.Context)
}

// RepairPlan represents a proposed fix for an error.
// Produced by Stage 2 (Planning).
type RepairPlan struct {
	PlanType   string                 // "restore_file", "repair_symbol", "restore_permissions"
	Priority   int                    // Lower = higher priority (0 = must fix first)
	TargetFile string                 // file to modify (relative to cwd)
	Action     string                 // "restore_full", "restore_symbol", "restore_permissions"
	Params     map[string]interface{} // action-specific parameters
	Reason     string                 // human-readable explanation
	ClueSource *ErrorClue             // the primary clue that generated this plan
	CluesFixed []*ErrorClue           // all clues this plan might fix
}

func (p *RepairPlan) String() string {
	return fmt.Sprintf("RepairPlan(type=%s, priority=%d, action=%s, target=%s)", p.PlanType, p.Priority, p.Action, p.TargetFile)
}

// RepairResult represents the outcome of attempting repairs.
// Produced by Stage 3 (Execution).
type RepairResult struct {
	Success        bool
	PlansAttempted []*RepairPlan
	FilesModified  []string
	ErrorMessage   string
	// Debug information
	CluesDetected  []*ErrorClue
	PlansGenerated []*RepairPlan
	Timings        map[string]time.Duration
}

func (r *RepairResult) String() string {
	status := "SUCCESS"
	if !r.Success {
		status = "FAILED"
	}
	return fmt.Sprintf("RepairResult(%s, modified=%d files)", status, len(r.FilesModified))
}

// ToDict converts RepairResult to a dictionary for JSON serialization
func (r *RepairResult) ToDict() map[string]interface{} {
	cluesDetected := make([]map[string]interface{}, 0)
	for _, c := range r.CluesDetected {
		if c != nil {
			cluesDetected = append(cluesDetected, map[string]interface{}{
				"clue_type":   c.ClueType,
				"confidence":  c.Confidence,
				"context":     c.Context,
				"source_line": c.SourceLine,
			})
		}
	}

	plansGenerated := make([]map[string]interface{}, 0)
	for _, p := range r.PlansGenerated {
		if p != nil {
			planDict := map[string]interface{}{
				"plan_type":         p.PlanType,
				"priority":          p.Priority,
				"target_file":       p.TargetFile,
				"action":            p.Action,
				"params":            p.Params,
				"reason":            p.Reason,
				"clues_fixed_count": len(p.CluesFixed),
			}
			if p.ClueSource != nil {
				planDict["clue_source"] = map[string]interface{}{
					"clue_type":   p.ClueSource.ClueType,
					"confidence":  p.ClueSource.Confidence,
					"context":     p.ClueSource.Context,
					"source_line": p.ClueSource.SourceLine,
				}
			} else {
				planDict["clue_source"] = nil
			}
			plansGenerated = append(plansGenerated, planDict)
		}
	}

	plansAttempted := make([]map[string]interface{}, 0)
	for _, p := range r.PlansAttempted {
		if p != nil {
			planDict := map[string]interface{}{
				"plan_type":         p.PlanType,
				"priority":          p.Priority,
				"target_file":       p.TargetFile,
				"action":            p.Action,
				"reason":            p.Reason,
				"clues_fixed_count": len(p.CluesFixed),
			}
			if p.ClueSource != nil {
				planDict["clue_source"] = map[string]interface{}{
					"clue_type":   p.ClueSource.ClueType,
					"confidence":  p.ClueSource.Confidence,
					"context":     p.ClueSource.Context,
					"source_line": p.ClueSource.SourceLine,
				}
			} else {
				planDict["clue_source"] = nil
			}
			plansAttempted = append(plansAttempted, planDict)
		}
	}

	// Convert timings to seconds (float)
	timingsDict := make(map[string]float64)
	for k, v := range r.Timings {
		timingsDict[k] = v.Seconds()
	}

	return map[string]interface{}{
		"success":         r.Success,
		"files_modified":  r.FilesModified,
		"error_message":   r.ErrorMessage,
		"clues_detected":  cluesDetected,
		"plans_generated": plansGenerated,
		"plans_attempted": plansAttempted,
		"timings":         timingsDict,
	}
}

// PartialFileInfo represents a file with missing lines
type PartialFileInfo struct {
	File      string // file path
	LineRatio string // e.g., "40/1001"
	Status    string // e.g., "M"
}

// GitState encapsulates git repository state
type GitState struct {
	Ref             string             // git ref to restore from (e.g., "HEAD")
	DeletedFiles    []string           // files deleted in working directory (sorted for determinism)
	GitToplevel     string             // git repository root directory
	PartialFiles    []*PartialFileInfo // files with missing lines
	SearchMode      bool               // True during Phase 2 of --search (element-level restoration)
	DiscoveredFiles map[string]bool    // Files discovered during Phase 1 of --search
}

// IsDiscoveredFile checks if a file was discovered during Phase 1 of --search
func (g *GitState) IsDiscoveredFile(filePath string) bool {
	if g.DiscoveredFiles == nil {
		return false
	}
	return g.DiscoveredFiles[filePath]
}

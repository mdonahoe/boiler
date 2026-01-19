// LinkerUndefinedSymbolsPlanner plans fixes for linker undefined symbol errors
package planners

import (
	"fmt"
	"path/filepath"
	"strings"

	"github.com/mdonahoe/boiler/src/boil/pipeline"
)

// LinkerUndefinedSymbolsPlanner plans fixes for linker undefined symbol errors
type LinkerUndefinedSymbolsPlanner struct{}

func NewLinkerUndefinedSymbolsPlanner() *LinkerUndefinedSymbolsPlanner {
	return &LinkerUndefinedSymbolsPlanner{}
}

func (p *LinkerUndefinedSymbolsPlanner) Name() string {
	return "LinkerUndefinedSymbolsPlanner"
}

func (p *LinkerUndefinedSymbolsPlanner) CanHandle(clueType string) bool {
	return clueType == "linker_undefined_symbols"
}

func (p *LinkerUndefinedSymbolsPlanner) Plan(clues []*pipeline.ErrorClue, gitState *pipeline.GitState) ([]*pipeline.RepairPlan, error) {
	// Collect all undefined symbols
	var symbols []string
	for _, clue := range clues {
		if clue.ClueType == "linker_undefined_symbols" {
			if sym := clue.Context["symbol"]; sym != "" {
				symbols = append(symbols, sym)
			}
		}
	}

	if len(symbols) == 0 {
		return nil, nil
	}

	// In search mode (Phase 2), use element-level restoration for discovered files
	if gitState.SearchMode {
		return p.planSearchMode(clues, gitState, symbols)
	}

	// Normal mode: restore full files
	return p.planNormalMode(clues, gitState, symbols)
}

// planNormalMode handles the normal (Phase 1) restoration using full file restores
func (p *LinkerUndefinedSymbolsPlanner) planNormalMode(clues []*pipeline.ErrorClue, gitState *pipeline.GitState, symbols []string) ([]*pipeline.RepairPlan, error) {
	var plans []*pipeline.RepairPlan

	// Check if lib.c is deleted - restore it first
	for _, deleted := range gitState.DeletedFiles {
		if filepath.Base(deleted) == "lib.c" {
			plans = append(plans, &pipeline.RepairPlan{
				PlanType:   "restore_file",
				Priority:   0,
				TargetFile: deleted,
				Action:     "restore_full",
				Params:     map[string]interface{}{"ref": gitState.Ref},
				Reason:     "Restore lib.c for undefined symbols",
				ClueSource: clues[0],
			})
			return plans, nil
		}
	}

	// Score deleted and partial C files by how many symbols they DEFINE (not just use)
	type fileScore struct {
		file  string
		score int
	}
	var scores []fileScore

	// Check deleted files
	for _, deleted := range gitState.DeletedFiles {
		if strings.HasSuffix(deleted, ".c") {
			// Check git content for function definitions
			content, err := getGitFileContent(deleted, gitState.Ref)
			if err != nil {
				continue
			}
			score := 0
			for _, sym := range symbols {
				// Look for function definitions, not just usages
				if containsFunctionDefinition(content, sym) {
					score++
				}
			}
			if score > 0 {
				scores = append(scores, fileScore{deleted, score})
			}
		}
	}

	// Check partial files (files that exist but are missing content)
	for _, partial := range gitState.PartialFiles {
		if strings.HasSuffix(partial.File, ".c") {
			// Check git content for function definitions
			content, err := getGitFileContent(partial.File, gitState.Ref)
			if err != nil {
				continue
			}
			score := 0
			for _, sym := range symbols {
				// Look for function definitions, not just usages
				if containsFunctionDefinition(content, sym) {
					score++
				}
			}
			if score > 0 {
				scores = append(scores, fileScore{partial.File, score})
			}
		}
	}

	// Restore highest scoring file
	if len(scores) > 0 {
		// Sort by score descending
		for i := 0; i < len(scores); i++ {
			for j := i + 1; j < len(scores); j++ {
				if scores[j].score > scores[i].score {
					scores[i], scores[j] = scores[j], scores[i]
				}
			}
		}
		plans = append(plans, &pipeline.RepairPlan{
			PlanType:   "restore_file",
			Priority:   0,
			TargetFile: scores[0].file,
			Action:     "restore_full",
			Params:     map[string]interface{}{"ref": gitState.Ref},
			Reason:     fmt.Sprintf("Restore %s (contains %d undefined symbols)", scores[0].file, scores[0].score),
			ClueSource: clues[0],
		})
	}

	return plans, nil
}

// planSearchMode handles Phase 2 restoration using element-level restores
// This restores only the specific functions/symbols needed, not entire files
func (p *LinkerUndefinedSymbolsPlanner) planSearchMode(clues []*pipeline.ErrorClue, gitState *pipeline.GitState, symbols []string) ([]*pipeline.RepairPlan, error) {
	var plans []*pipeline.RepairPlan

	// For each symbol, find which file contains its definition and restore just that function
	for _, sym := range symbols {
		// First check partial files (files that exist but are incomplete)
		for _, partial := range gitState.PartialFiles {
			if !strings.HasSuffix(partial.File, ".c") {
				continue
			}
			// Skip files that weren't discovered in Phase 1
			if !gitState.IsDiscoveredFile(partial.File) {
				continue
			}
			content, err := getGitFileContent(partial.File, gitState.Ref)
			if err != nil {
				continue
			}
			if containsFunctionDefinition(content, sym) {
				plans = append(plans, &pipeline.RepairPlan{
					PlanType:   "restore_c_element",
					Priority:   0,
					TargetFile: partial.File,
					Action:     "restore_c_element",
					Params: map[string]interface{}{
						"element_name": sym,
						"element_type": "function",
						"ref":          gitState.Ref,
					},
					Reason:     fmt.Sprintf("Restore function %s in %s", sym, partial.File),
					ClueSource: clues[0],
				})
				break // Found the symbol, move to next
			}
		}

		// If we didn't find in partial files, check deleted files
		// (but only discovered ones - non-discovered files should use restore_full)
		for _, deleted := range gitState.DeletedFiles {
			if !strings.HasSuffix(deleted, ".c") {
				continue
			}
			// Skip files that weren't discovered in Phase 1
			if !gitState.IsDiscoveredFile(deleted) {
				continue
			}
			content, err := getGitFileContent(deleted, gitState.Ref)
			if err != nil {
				continue
			}
			if containsFunctionDefinition(content, sym) {
				// File was discovered but is now deleted again (after reset)
				// We need to first restore an empty file, then add the function
				plans = append(plans, &pipeline.RepairPlan{
					PlanType:   "restore_c_element",
					Priority:   0,
					TargetFile: deleted,
					Action:     "restore_c_element",
					Params: map[string]interface{}{
						"element_name": sym,
						"element_type": "function",
						"ref":          gitState.Ref,
					},
					Reason:     fmt.Sprintf("Restore function %s in %s", sym, deleted),
					ClueSource: clues[0],
				})
				break // Found the symbol, move to next
			}
		}
	}

	// If no element-level plans could be made, fall back to file-level for non-discovered files
	if len(plans) == 0 {
		// Only restore files that are NOT discovered (new files found during Phase 2)
		for _, deleted := range gitState.DeletedFiles {
			if strings.HasSuffix(deleted, ".c") && !gitState.IsDiscoveredFile(deleted) {
				content, err := getGitFileContent(deleted, gitState.Ref)
				if err != nil {
					continue
				}
				for _, sym := range symbols {
					if containsFunctionDefinition(content, sym) {
						plans = append(plans, &pipeline.RepairPlan{
							PlanType:   "restore_file",
							Priority:   0,
							TargetFile: deleted,
							Action:     "restore_full",
							Params:     map[string]interface{}{"ref": gitState.Ref},
							Reason:     fmt.Sprintf("Restore %s (contains undefined symbol %s)", deleted, sym),
							ClueSource: clues[0],
						})
						return plans, nil
					}
				}
			}
		}
	}

	return plans, nil
}

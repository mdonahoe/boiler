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
	var plans []*pipeline.RepairPlan

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

	// Score deleted C files by how many symbols they contain
	type fileScore struct {
		file  string
		score int
	}
	var scores []fileScore

	for _, deleted := range gitState.DeletedFiles {
		if strings.HasSuffix(deleted, ".c") {
			// Check git content for symbols
			content, err := getGitFileContent(deleted, gitState.Ref)
			if err != nil {
				continue
			}
			score := 0
			for _, sym := range symbols {
				if strings.Contains(content, sym) {
					score++
				}
			}
			if score > 0 {
				scores = append(scores, fileScore{deleted, score})
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

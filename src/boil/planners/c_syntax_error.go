// CSyntaxErrorPlanner plans fixes for C syntax errors
package planners

import (
	"fmt"

	"github.com/mdonahoe/boiler/src/boil/pipeline"
)

// CSyntaxErrorPlanner plans fixes for C syntax errors
type CSyntaxErrorPlanner struct{}

func NewCSyntaxErrorPlanner() *CSyntaxErrorPlanner {
	return &CSyntaxErrorPlanner{}
}

func (p *CSyntaxErrorPlanner) Name() string {
	return "CSyntaxErrorPlanner"
}

func (p *CSyntaxErrorPlanner) CanHandle(clueType string) bool {
	return clueType == "c_syntax_error_in_header" || clueType == "c_syntax_error_in_source"
}

func (p *CSyntaxErrorPlanner) Plan(clues []*pipeline.ErrorClue, gitState *pipeline.GitState) ([]*pipeline.RepairPlan, error) {
	var plans []*pipeline.RepairPlan
	for _, clue := range clues {
		if !p.CanHandle(clue.ClueType) {
			continue
		}

		filePath := clue.Context["file_path"]
		if filePath == "" {
			continue
		}

		// Restore the file with syntax error
		plans = append(plans, &pipeline.RepairPlan{
			PlanType:   "restore_file",
			Priority:   0,
			TargetFile: filePath,
			Action:     "restore_full",
			Params:     map[string]interface{}{"ref": gitState.Ref},
			Reason:     fmt.Sprintf("Restore %s (syntax error)", filePath),
			ClueSource: clue,
		})
	}
	return plans, nil
}

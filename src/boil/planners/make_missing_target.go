// MakeMissingTargetPlanner plans fixes for missing target errors
package planners

import (
	"fmt"
	"strings"

	"github.com/mdonahoe/boiler/src/boil/pipeline"
)

// MakeMissingTargetPlanner plans fixes for missing target errors
type MakeMissingTargetPlanner struct{}

func NewMakeMissingTargetPlanner() *MakeMissingTargetPlanner {
	return &MakeMissingTargetPlanner{}
}

func (p *MakeMissingTargetPlanner) Name() string {
	return "MakeMissingTargetPlanner"
}

func (p *MakeMissingTargetPlanner) CanHandle(clueType string) bool {
	return clueType == "make_missing_target"
}

func (p *MakeMissingTargetPlanner) Plan(clues []*pipeline.ErrorClue, gitState *pipeline.GitState) ([]*pipeline.RepairPlan, error) {
	var plans []*pipeline.RepairPlan
	for _, clue := range clues {
		if clue.ClueType != "make_missing_target" {
			continue
		}

		target := clue.Context["target"]
		if target == "" {
			continue
		}

		// For .o files, try to restore corresponding source files
		if strings.HasSuffix(target, ".o") {
			baseName := strings.TrimSuffix(target, ".o")
			sourceExts := []string{".c", ".cpp", ".cc", ".cxx"}
			for _, ext := range sourceExts {
				sourceFile := baseName + ext
				if found := findFileInDeleted(sourceFile, gitState.DeletedFiles); found != "" {
					plans = append(plans, &pipeline.RepairPlan{
						PlanType:   "restore_file",
						Priority:   0,
						TargetFile: found,
						Action:     "restore_full",
						Params:     map[string]interface{}{"ref": gitState.Ref},
						Reason:     fmt.Sprintf("Restore %s for target %s", found, target),
						ClueSource: clue,
					})
					break
				}
			}
		} else {
			// Try to restore the target file directly
			if found := findFileInDeleted(target, gitState.DeletedFiles); found != "" {
				plans = append(plans, &pipeline.RepairPlan{
					PlanType:   "restore_file",
					Priority:   0,
					TargetFile: found,
					Action:     "restore_full",
					Params:     map[string]interface{}{"ref": gitState.Ref},
					Reason:     fmt.Sprintf("Restore missing target %s", target),
					ClueSource: clue,
				})
			}
		}
	}
	return plans, nil
}

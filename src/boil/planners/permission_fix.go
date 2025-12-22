// PermissionFixPlanner plans fixes for permission denied errors
package planners

import (
	"fmt"
	"path/filepath"
	"strings"

	"github.com/mdonahoe/boiler/src/boil/pipeline"
)

// PermissionFixPlanner plans fixes for permission denied errors
type PermissionFixPlanner struct{}

func NewPermissionFixPlanner() *PermissionFixPlanner {
	return &PermissionFixPlanner{}
}

func (p *PermissionFixPlanner) Name() string {
	return "PermissionFixPlanner"
}

func (p *PermissionFixPlanner) CanHandle(clueType string) bool {
	return strings.HasSuffix(clueType, "permission_denied")
}

func (p *PermissionFixPlanner) Plan(clues []*pipeline.ErrorClue, gitState *pipeline.GitState) ([]*pipeline.RepairPlan, error) {
	var plans []*pipeline.RepairPlan
	for _, clue := range clues {
		if !strings.HasSuffix(clue.ClueType, "permission_denied") {
			continue
		}

		filePath := clue.Context["file_path"]
		if filePath == "" {
			continue
		}

		if filepath.IsAbs(filePath) {
			filePath, _ = filepath.Rel(".", filePath)
		}

		priority := 1 // Medium priority if file exists
		if !fileExists(filePath) {
			priority = 0 // High priority if file missing
		}

		plans = append(plans, &pipeline.RepairPlan{
			PlanType:   "restore_file",
			Priority:   priority,
			TargetFile: filePath,
			Action:     "restore_full",
			Params:     map[string]interface{}{"ref": gitState.Ref},
			Reason:     fmt.Sprintf("Fix permissions for %s", filePath),
			ClueSource: clue,
		})
	}
	return plans, nil
}

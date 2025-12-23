// MissingDirectoryPlanner plans fixes for missing directories and glob patterns
package planners

import (
	"fmt"
	"path/filepath"
	"strings"

	"github.com/mdonahoe/boiler/src/boil/pipeline"
)

// MissingDirectoryPlanner plans fixes for missing directories and glob patterns
type MissingDirectoryPlanner struct{}

func NewMissingDirectoryPlanner() *MissingDirectoryPlanner {
	return &MissingDirectoryPlanner{}
}

func (p *MissingDirectoryPlanner) Name() string {
	return "MissingDirectoryPlanner"
}

func (p *MissingDirectoryPlanner) CanHandle(clueType string) bool {
	return strings.HasPrefix(clueType, "missing_file")
}

func (p *MissingDirectoryPlanner) Plan(clues []*pipeline.ErrorClue, gitState *pipeline.GitState) ([]*pipeline.RepairPlan, error) {
	var plans []*pipeline.RepairPlan
	for _, clue := range clues {
		if !strings.HasPrefix(clue.ClueType, "missing_file") {
			continue
		}

		filePath := clue.Context["file_path"]
		if filePath == "" {
			continue
		}

		// Make path relative if absolute
		originalFilePath := filePath
		if filepath.IsAbs(filePath) {
			rel, err := filepath.Rel(".", filePath)
			if err == nil && rel != "" {
				filePath = rel
			}
			// If Rel fails, filePath stays as the original absolute path
		}

		// If path is still absolute-ish (contains ../, starts with /, or Rel failed),
		// try to find a matching path suffix from deleted files
		if strings.Contains(filePath, "../") || strings.HasPrefix(filePath, "/") || (filepath.IsAbs(originalFilePath) && filePath == originalFilePath) {
			filePath = findMatchingDirectoryPath(originalFilePath, gitState.DeletedFiles)
			if filePath == "" {
				continue
			}
		}

		// Check if glob pattern
		if strings.Contains(filePath, "*") || strings.Contains(filePath, "?") {
			matchingFiles := matchGlob(filePath, gitState.DeletedFiles)
			for _, deleted := range matchingFiles {
				plans = append(plans, &pipeline.RepairPlan{
					PlanType:   "restore_file",
					Priority:   0,
					TargetFile: deleted,
					Action:     "restore_full",
					Params:     map[string]interface{}{"ref": gitState.Ref},
					Reason:     fmt.Sprintf("File %s is missing (matches glob %s)", deleted, filePath),
					ClueSource: clue,
				})
			}
			continue
		}

		// Check if directory
		var directoryFiles []string
		for _, deleted := range gitState.DeletedFiles {
			if strings.HasPrefix(deleted, filePath+"/") {
				directoryFiles = append(directoryFiles, deleted)
			}
		}
		if len(directoryFiles) > 0 {
			for _, deleted := range directoryFiles {
				plans = append(plans, &pipeline.RepairPlan{
					PlanType:   "restore_file",
					Priority:   0,
					TargetFile: deleted,
					Action:     "restore_full",
					Params:     map[string]interface{}{"ref": gitState.Ref},
					Reason:     fmt.Sprintf("File %s is missing (part of %s directory)", deleted, filePath),
					ClueSource: clue,
				})
			}
		}
	}
	return plans, nil
}

// MissingFilePlanner plans fixes for generic missing file errors
package planners

import (
	"fmt"
	"path/filepath"
	"strings"

	"github.com/mdonahoe/boiler/src/boil/pipeline"
)

// MissingFilePlanner plans fixes for generic missing file errors
type MissingFilePlanner struct{}

func NewMissingFilePlanner() *MissingFilePlanner {
	return &MissingFilePlanner{}
}

func (p *MissingFilePlanner) Name() string {
	return "MissingFilePlanner"
}

func (p *MissingFilePlanner) CanHandle(clueType string) bool {
	return strings.HasPrefix(clueType, "missing_file")
}

func (p *MissingFilePlanner) Plan(clues []*pipeline.ErrorClue, gitState *pipeline.GitState) ([]*pipeline.RepairPlan, error) {
	var plans []*pipeline.RepairPlan
	for _, clue := range clues {
		if !strings.HasPrefix(clue.ClueType, "missing_file") {
			continue
		}
		cluePlans := p.planForClue(clue, gitState)
		plans = append(plans, cluePlans...)
	}
	return plans, nil
}

func (p *MissingFilePlanner) planForClue(clue *pipeline.ErrorClue, gitState *pipeline.GitState) []*pipeline.RepairPlan {
	filePath := clue.Context["file_path"]
	if filePath == "" {
		return nil
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
		// First check if it's a directory
		dirPath := findMatchingDirectoryPath(originalFilePath, gitState.DeletedFiles)
		if dirPath != "" {
			// It's a directory - let MissingDirectoryPlanner handle it
			return nil
		}
		// Try to find as a file
		filePath = findMatchingFilePath(originalFilePath, gitState.DeletedFiles)
		if filePath == "" {
			return nil
		}
	}

	// Skip glob patterns (handled by MissingDirectoryPlanner)
	if strings.Contains(filePath, "*") || strings.Contains(filePath, "?") {
		return nil
	}

	// Skip directories (handled by MissingDirectoryPlanner)
	for _, deleted := range gitState.DeletedFiles {
		if strings.HasPrefix(deleted, filePath+"/") {
			return nil
		}
	}

	// Find the file in deleted files
	actualPath := findFileInDeleted(filePath, gitState.DeletedFiles)

	// If still not found but file exists locally, check if it matches git
	if actualPath == "" && fileExists(filePath) {
		// File exists - no need to restore
		return nil
	}

	targetFile := actualPath
	if targetFile == "" {
		targetFile = filePath
	}

	return []*pipeline.RepairPlan{{
		PlanType:   "restore_file",
		Priority:   0,
		TargetFile: targetFile,
		Action:     "restore_full",
		Params:     map[string]interface{}{"ref": gitState.Ref},
		Reason:     fmt.Sprintf("File %s is missing", filePath),
		ClueSource: clue,
	}}
}

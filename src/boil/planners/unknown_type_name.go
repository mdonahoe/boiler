// UnknownTypeNamePlanner plans fixes for unknown type name errors
package planners

import (
	"fmt"
	"os/exec"
	"strings"

	"github.com/mdonahoe/boiler/src/boil/pipeline"
)

// UnknownTypeNamePlanner plans fixes for unknown type name errors
type UnknownTypeNamePlanner struct{}

func NewUnknownTypeNamePlanner() *UnknownTypeNamePlanner {
	return &UnknownTypeNamePlanner{}
}

func (p *UnknownTypeNamePlanner) Name() string {
	return "UnknownTypeNamePlanner"
}

func (p *UnknownTypeNamePlanner) CanHandle(clueType string) bool {
	return clueType == "unknown_type_name"
}

func (p *UnknownTypeNamePlanner) Plan(clues []*pipeline.ErrorClue, gitState *pipeline.GitState) ([]*pipeline.RepairPlan, error) {
	var plans []*pipeline.RepairPlan
	for _, clue := range clues {
		if clue.ClueType != "unknown_type_name" {
			continue
		}

		filePath := clue.Context["file_path"]
		typeName := clue.Context["type_name"]

		if filePath == "" || typeName == "" || !fileExists(filePath) {
			continue
		}

		// Search git for headers defining this type
		header := findHeaderForType(typeName, gitState)
		if header == "" {
			continue
		}

		plans = append(plans, &pipeline.RepairPlan{
			PlanType:   "restore_c_element",
			Priority:   0,
			TargetFile: filePath,
			Action:     "restore_c_element",
			Params: map[string]interface{}{
				"element_name": header,
				"element_type": "include",
			},
			Reason:     fmt.Sprintf("Add #include for type %s", typeName),
			ClueSource: clue,
		})
	}
	return plans, nil
}

func findHeaderForType(typeName string, gitState *pipeline.GitState) string {
	// Search git for headers defining this type
	cmd := exec.Command("git", "grep", "-l", typeName, gitState.Ref, "--", "*.h")
	output, err := cmd.Output()
	if err != nil {
		return ""
	}

	lines := strings.Split(strings.TrimSpace(string(output)), "\n")
	for _, line := range lines {
		// Remove ref prefix
		parts := strings.SplitN(line, ":", 2)
		if len(parts) == 2 {
			header := parts[1]
			// Prefer api.h or public includes
			if strings.Contains(header, "api.h") || strings.Contains(header, "/include/") {
				// Extract include path
				if idx := strings.Index(header, "/include/"); idx >= 0 {
					return header[idx+9:] // Skip "/include/"
				}
				return header
			}
		}
	}

	// Return first result if no preferred match
	if len(lines) > 0 {
		parts := strings.SplitN(lines[0], ":", 2)
		if len(parts) == 2 {
			return parts[1]
		}
	}
	return ""
}

// MissingCIncludePlanner plans fixes for missing C includes
package planners

import (
	"fmt"

	"github.com/mdonahoe/boiler/src/boil/pipeline"
)

// MissingCIncludePlanner plans fixes for missing C includes
type MissingCIncludePlanner struct{}

func NewMissingCIncludePlanner() *MissingCIncludePlanner {
	return &MissingCIncludePlanner{}
}

func (p *MissingCIncludePlanner) Name() string {
	return "MissingCIncludePlanner"
}

func (p *MissingCIncludePlanner) CanHandle(clueType string) bool {
	return clueType == "missing_c_include"
}

func (p *MissingCIncludePlanner) Plan(clues []*pipeline.ErrorClue, gitState *pipeline.GitState) ([]*pipeline.RepairPlan, error) {
	var plans []*pipeline.RepairPlan

	// Struct name to header mapping
	structToHeader := map[string]string{
		"termios":   "termios.h",
		"winsize":   "sys/ioctl.h",
		"stat":      "sys/stat.h",
		"tm":        "time.h",
		"sigaction": "signal.h",
		"dirent":    "dirent.h",
	}

	for _, clue := range clues {
		if clue.ClueType != "missing_c_include" {
			continue
		}

		filePath := clue.Context["file_path"]
		if filePath == "" || !fileExists(filePath) {
			continue
		}

		// Get the include to add
		include := clue.Context["suggested_include"]
		if include == "" {
			if structName := clue.Context["struct_name"]; structName != "" {
				include = structToHeader[structName]
			}
		}

		if include == "" {
			continue
		}

		plans = append(plans, &pipeline.RepairPlan{
			PlanType:   "restore_c_element",
			Priority:   0,
			TargetFile: filePath,
			Action:     "restore_c_element",
			Params: map[string]interface{}{
				"element_name": include,
				"element_type": "include",
			},
			Reason:     fmt.Sprintf("Add #include <%s>", include),
			ClueSource: clue,
		})
	}
	return plans, nil
}

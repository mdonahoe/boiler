// PythonNameErrorPlanner plans fixes for Python NameError
package planners

import (
	"fmt"

	"github.com/mdonahoe/boiler/src/boil/pipeline"
)

// PythonNameErrorPlanner plans fixes for Python NameError
type PythonNameErrorPlanner struct{}

func NewPythonNameErrorPlanner() *PythonNameErrorPlanner {
	return &PythonNameErrorPlanner{}
}

func (p *PythonNameErrorPlanner) Name() string {
	return "PythonNameErrorPlanner"
}

func (p *PythonNameErrorPlanner) CanHandle(clueType string) bool {
	return clueType == "python_name_error"
}

func (p *PythonNameErrorPlanner) Plan(clues []*pipeline.ErrorClue, gitState *pipeline.GitState) ([]*pipeline.RepairPlan, error) {
	var plans []*pipeline.RepairPlan
	for _, clue := range clues {
		if clue.ClueType != "python_name_error" {
			continue
		}

		filePath := clue.Context["file_path"]
		elementName := clue.Context["undefined_name"]
		lineNumber := clue.Context["line_number"]

		if filePath == "" || elementName == "" {
			continue
		}

		if !fileExists(filePath) {
			continue
		}

		plans = append(plans, &pipeline.RepairPlan{
			PlanType:   "restore_python_element",
			Priority:   0,
			TargetFile: filePath,
			Action:     "restore_python_element",
			Params: map[string]interface{}{
				"element_name": elementName,
				"line_number":  lineNumber,
			},
			Reason:     fmt.Sprintf("Restore missing Python element '%s'", elementName),
			ClueSource: clue,
		})
	}
	return plans, nil
}

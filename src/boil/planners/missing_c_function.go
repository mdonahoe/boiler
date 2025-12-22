// MissingCFunctionPlanner plans fixes for missing C functions
package planners

import (
	"fmt"

	"github.com/mdonahoe/boiler/src/boil/pipeline"
)

// MissingCFunctionPlanner plans fixes for missing C functions
type MissingCFunctionPlanner struct{}

func NewMissingCFunctionPlanner() *MissingCFunctionPlanner {
	return &MissingCFunctionPlanner{}
}

func (p *MissingCFunctionPlanner) Name() string {
	return "MissingCFunctionPlanner"
}

func (p *MissingCFunctionPlanner) CanHandle(clueType string) bool {
	return clueType == "missing_c_function"
}

func (p *MissingCFunctionPlanner) Plan(clues []*pipeline.ErrorClue, gitState *pipeline.GitState) ([]*pipeline.RepairPlan, error) {
	var plans []*pipeline.RepairPlan

	// Common stdlib functions to their headers
	stdlibMap := map[string]string{
		"printf": "stdio.h", "fprintf": "stdio.h", "sprintf": "stdio.h",
		"scanf": "stdio.h", "fopen": "stdio.h", "fclose": "stdio.h",
		"malloc": "stdlib.h", "free": "stdlib.h", "realloc": "stdlib.h",
		"exit": "stdlib.h", "atoi": "stdlib.h", "atof": "stdlib.h",
		"strlen": "string.h", "strcpy": "string.h", "strcat": "string.h",
		"strcmp": "string.h", "memcpy": "string.h", "memset": "string.h",
		"isalpha": "ctype.h", "isdigit": "ctype.h", "isspace": "ctype.h",
		"time": "time.h", "localtime": "time.h", "strftime": "time.h",
		"assert": "assert.h",
	}

	for _, clue := range clues {
		if clue.ClueType != "missing_c_function" {
			continue
		}

		filePath := clue.Context["file_path"]
		funcName := clue.Context["function_name"]
		if funcName == "" {
			funcName = clue.Context["identifier"]
		}

		if filePath == "" || funcName == "" || !fileExists(filePath) {
			continue
		}

		// Check if it's a stdlib function
		if header, ok := stdlibMap[funcName]; ok {
			plans = append(plans, &pipeline.RepairPlan{
				PlanType:   "restore_c_element",
				Priority:   0,
				TargetFile: filePath,
				Action:     "restore_c_element",
				Params: map[string]interface{}{
					"element_name": header,
					"element_type": "include",
				},
				Reason:     fmt.Sprintf("Add #include <%s> for %s", header, funcName),
				ClueSource: clue,
			})
		} else {
			// User-defined function - restore from git
			plans = append(plans, &pipeline.RepairPlan{
				PlanType:   "restore_c_element",
				Priority:   0,
				TargetFile: filePath,
				Action:     "restore_c_element",
				Params: map[string]interface{}{
					"element_name": funcName,
					"element_type": "function",
				},
				Reason:     fmt.Sprintf("Restore function %s", funcName),
				ClueSource: clue,
			})
		}
	}
	return plans, nil
}

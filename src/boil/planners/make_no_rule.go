// MakeNoRulePlanner plans fixes for 'No rule to make target' errors
package planners

import (
	"fmt"
	"path/filepath"
	"strings"

	"github.com/mdonahoe/boiler/src/boil/pipeline"
)

// MakeNoRulePlanner plans fixes for 'No rule to make target' errors
type MakeNoRulePlanner struct{}

func NewMakeNoRulePlanner() *MakeNoRulePlanner {
	return &MakeNoRulePlanner{}
}

func (p *MakeNoRulePlanner) Name() string {
	return "MakeNoRulePlanner"
}

func (p *MakeNoRulePlanner) CanHandle(clueType string) bool {
	return clueType == "make_no_rule"
}

func (p *MakeNoRulePlanner) Plan(clues []*pipeline.ErrorClue, gitState *pipeline.GitState) ([]*pipeline.RepairPlan, error) {
	var noRuleClues []*pipeline.ErrorClue
	for _, clue := range clues {
		if clue.ClueType == "make_no_rule" {
			noRuleClues = append(noRuleClues, clue)
		}
	}
	if len(noRuleClues) == 0 {
		return nil, nil
	}

	// Look for Makefiles in deleted files
	makefileNames := []string{"Makefile", "makefile", "GNUmakefile"}
	var rootMakefiles, subdirMakefiles []string

	for _, name := range makefileNames {
		for _, deleted := range gitState.DeletedFiles {
			base := filepath.Base(deleted)
			if base == name {
				if deleted == name || !strings.Contains(deleted, "/") {
					rootMakefiles = append(rootMakefiles, deleted)
				} else {
					subdirMakefiles = append(subdirMakefiles, deleted)
				}
			}
		}
	}

	prioritized := append(rootMakefiles, subdirMakefiles...)
	if len(prioritized) == 0 {
		return nil, nil
	}

	makefileToRestore := prioritized[0]
	return []*pipeline.RepairPlan{{
		PlanType:   "restore_file",
		Priority:   0,
		TargetFile: makefileToRestore,
		Action:     "restore_full",
		Params:     map[string]interface{}{"ref": gitState.Ref},
		Reason:     fmt.Sprintf("Restore %s (no rule to make target '%s')", makefileToRestore, noRuleClues[0].Context["target"]),
		ClueSource: noRuleClues[0],
	}}, nil
}

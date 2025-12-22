// TestFailurePlanner plans fixes for test failures
package planners

import (
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"strings"

	"github.com/mdonahoe/boiler/src/boil/pipeline"
)

// TestFailurePlanner plans fixes for test failures
type TestFailurePlanner struct{}

func NewTestFailurePlanner() *TestFailurePlanner {
	return &TestFailurePlanner{}
}

func (p *TestFailurePlanner) Name() string {
	return "TestFailurePlanner"
}

func (p *TestFailurePlanner) CanHandle(clueType string) bool {
	return clueType == "test_failure" || clueType == "test_docstring_with_missing_file" ||
		clueType == "c_test_failure" || clueType == "test_assertion_with_filename"
}

func (p *TestFailurePlanner) Plan(clues []*pipeline.ErrorClue, gitState *pipeline.GitState) ([]*pipeline.RepairPlan, error) {
	var plans []*pipeline.RepairPlan
	seenTargets := make(map[string]bool)

	for _, clue := range clues {
		if !p.CanHandle(clue.ClueType) {
			continue
		}

		// For assertion/docstring types, use suspected_file directly
		if suspectedFile := clue.Context["suspected_file"]; suspectedFile != "" {
			if found := findFileInDeleted(suspectedFile, gitState.DeletedFiles); found != "" {
				if !seenTargets[found] {
					plans = append(plans, &pipeline.RepairPlan{
						PlanType:   "restore_file",
						Priority:   0,
						TargetFile: found,
						Action:     "restore_full",
						Params:     map[string]interface{}{"ref": gitState.Ref},
						Reason:     fmt.Sprintf("Restore %s referenced in test", found),
						ClueSource: clue,
					})
					seenTargets[found] = true
				}
			}
		}

		// For test_failure clues, read the test file and extract file references
		if clue.ClueType == "test_failure" {
			testFile := clue.Context["test_file"]
			lineNumberStr := clue.Context["line_number"]
			if testFile != "" && lineNumberStr != "" {
				lineNumber := 0
				fmt.Sscanf(lineNumberStr, "%d", &lineNumber)
				referencedFiles := extractFileReferences(testFile, lineNumber)
				for _, ref := range referencedFiles {
					if found := findFileInDeleted(ref, gitState.DeletedFiles); found != "" {
						if !seenTargets[found] {
							plans = append(plans, &pipeline.RepairPlan{
								PlanType:   "restore_file",
								Priority:   0,
								TargetFile: found,
								Action:     "restore_full",
								Params:     map[string]interface{}{"ref": gitState.Ref},
								Reason:     fmt.Sprintf("Restore %s referenced in test at %s:%d", found, filepath.Base(testFile), lineNumber),
								ClueSource: clue,
							})
							seenTargets[found] = true
						}
					}
				}
			}
		}
	}

	// If no specific plans, restore partial files
	if len(plans) == 0 && len(gitState.PartialFiles) > 0 {
		for _, partial := range gitState.PartialFiles {
			plans = append(plans, &pipeline.RepairPlan{
				PlanType:   "restore_file",
				Priority:   0,
				TargetFile: partial.File,
				Action:     "restore_full",
				Params:     map[string]interface{}{"ref": gitState.Ref},
				Reason:     fmt.Sprintf("Restore partial file %s (%s lines)", partial.File, partial.LineRatio),
				ClueSource: clues[0],
			})
		}
	}
	return plans, nil
}

// extractFileReferences reads the test file around the failure line and extracts
// file references from patterns like command=["./dim", "example.c"]
func extractFileReferences(testFile string, lineNumber int) []string {
	var referencedFiles []string

	content, err := os.ReadFile(testFile)
	if err != nil {
		return nil
	}

	lines := strings.Split(string(content), "\n")

	// Line numbers are 1-indexed, convert to 0-indexed for array access
	lineIdx := lineNumber - 1

	// Get context around the failure line (10 lines before, 20 lines after)
	startLine := lineIdx - 10
	if startLine < 0 {
		startLine = 0
	}
	endLine := lineIdx + 20
	if endLine > len(lines) {
		endLine = len(lines)
	}

	contextLines := lines[startLine:endLine]
	contextText := strings.Join(contextLines, "\n")

	// File extensions to look for
	fileExts := `py|txt|md|c|h|cpp|hpp|json|yaml|yml|sh`

	// Pattern 1: Command arguments with filenames (Python tests)
	// Matches: command=["./dim", "filename.txt"] or command=["./dim", 'filename.txt']
	commandPattern := regexp.MustCompile(`command\s*=\s*\[[^\]]*["']([^"']+\.(?:` + fileExts + `))["']`)
	for _, match := range commandPattern.FindAllStringSubmatch(contextText, -1) {
		if len(match) > 1 {
			referencedFiles = append(referencedFiles, match[1])
		}
	}

	// Pattern 2: assertIn/assertEqual with filenames (Python tests)
	assertPattern := regexp.MustCompile(`assert(?:In|Equal|NotIn|NotEqual)\s*\([^)]*["']([^"']+\.(?:` + fileExts + `))["']`)
	for _, match := range assertPattern.FindAllStringSubmatch(contextText, -1) {
		if len(match) > 1 {
			referencedFiles = append(referencedFiles, match[1])
		}
	}

	// Pattern 3: open() calls with filenames
	openPattern := regexp.MustCompile(`open\s*\(\s*["']([^"']+\.(?:` + fileExts + `))["']`)
	for _, match := range openPattern.FindAllStringSubmatch(contextText, -1) {
		if len(match) > 1 {
			referencedFiles = append(referencedFiles, match[1])
		}
	}

	// Pattern 4: C string literals with data file extensions
	cStringPattern := regexp.MustCompile(`["'](\./)?([^"']+\.(?:txt|md|json|yaml|yml|sh|dat))["']`)
	for _, match := range cStringPattern.FindAllStringSubmatch(contextText, -1) {
		if len(match) > 2 {
			referencedFiles = append(referencedFiles, match[2])
		}
	}

	return referencedFiles
}

// All planner implementations for the boil pipeline
package planners

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
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
	if filepath.IsAbs(filePath) {
		filePath, _ = filepath.Rel(".", filePath)
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
		if filepath.IsAbs(filePath) {
			filePath, _ = filepath.Rel(".", filePath)
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
			if pipeline.IsVerbose() {
				fmt.Printf("[TestFailurePlanner] Processing test_failure: file=%s, line=%s\n", testFile, lineNumberStr)
			}
			if testFile != "" && lineNumberStr != "" {
				lineNumber := 0
				fmt.Sscanf(lineNumberStr, "%d", &lineNumber)
				referencedFiles := extractFileReferences(testFile, lineNumber, gitState)
				if pipeline.IsVerbose() {
					fmt.Printf("[TestFailurePlanner] Found %d file references: %v\n", len(referencedFiles), referencedFiles)
				}
				for _, ref := range referencedFiles {
					if found := findFileInDeleted(ref, gitState.DeletedFiles); found != "" {
						if !seenTargets[found] {
							if pipeline.IsVerbose() {
								fmt.Printf("[TestFailurePlanner] Adding plan to restore %s (ref=%s)\n", found, ref)
							}
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
					} else if pipeline.IsVerbose() {
						fmt.Printf("[TestFailurePlanner] File %s not in deleted files\n", ref)
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

// LinkerUndefinedSymbolsPlanner plans fixes for linker undefined symbol errors
type LinkerUndefinedSymbolsPlanner struct{}

func NewLinkerUndefinedSymbolsPlanner() *LinkerUndefinedSymbolsPlanner {
	return &LinkerUndefinedSymbolsPlanner{}
}

func (p *LinkerUndefinedSymbolsPlanner) Name() string {
	return "LinkerUndefinedSymbolsPlanner"
}

func (p *LinkerUndefinedSymbolsPlanner) CanHandle(clueType string) bool {
	return clueType == "linker_undefined_symbols"
}

func (p *LinkerUndefinedSymbolsPlanner) Plan(clues []*pipeline.ErrorClue, gitState *pipeline.GitState) ([]*pipeline.RepairPlan, error) {
	var plans []*pipeline.RepairPlan

	// Collect all undefined symbols
	var symbols []string
	for _, clue := range clues {
		if clue.ClueType == "linker_undefined_symbols" {
			if sym := clue.Context["symbol"]; sym != "" {
				symbols = append(symbols, sym)
			}
		}
	}

	if len(symbols) == 0 {
		return nil, nil
	}

	// Check if lib.c is deleted - restore it first
	for _, deleted := range gitState.DeletedFiles {
		if filepath.Base(deleted) == "lib.c" {
			plans = append(plans, &pipeline.RepairPlan{
				PlanType:   "restore_file",
				Priority:   0,
				TargetFile: deleted,
				Action:     "restore_full",
				Params:     map[string]interface{}{"ref": gitState.Ref},
				Reason:     "Restore lib.c for undefined symbols",
				ClueSource: clues[0],
			})
			return plans, nil
		}
	}

	// Score deleted C files by how many symbols they contain
	type fileScore struct {
		file  string
		score int
	}
	var scores []fileScore

	for _, deleted := range gitState.DeletedFiles {
		if strings.HasSuffix(deleted, ".c") {
			// Check git content for symbols
			content, err := getGitFileContent(deleted, gitState.Ref)
			if err != nil {
				continue
			}
			score := 0
			for _, sym := range symbols {
				if strings.Contains(content, sym) {
					score++
				}
			}
			if score > 0 {
				scores = append(scores, fileScore{deleted, score})
			}
		}
	}

	// Restore highest scoring file
	if len(scores) > 0 {
		// Sort by score descending
		for i := 0; i < len(scores); i++ {
			for j := i + 1; j < len(scores); j++ {
				if scores[j].score > scores[i].score {
					scores[i], scores[j] = scores[j], scores[i]
				}
			}
		}
		plans = append(plans, &pipeline.RepairPlan{
			PlanType:   "restore_file",
			Priority:   0,
			TargetFile: scores[0].file,
			Action:     "restore_full",
			Params:     map[string]interface{}{"ref": gitState.Ref},
			Reason:     fmt.Sprintf("Restore %s (contains %d undefined symbols)", scores[0].file, scores[0].score),
			ClueSource: clues[0],
		})
	}

	return plans, nil
}

// CSyntaxErrorPlanner plans fixes for C syntax errors
type CSyntaxErrorPlanner struct{}

func NewCSyntaxErrorPlanner() *CSyntaxErrorPlanner {
	return &CSyntaxErrorPlanner{}
}

func (p *CSyntaxErrorPlanner) Name() string {
	return "CSyntaxErrorPlanner"
}

func (p *CSyntaxErrorPlanner) CanHandle(clueType string) bool {
	return clueType == "c_syntax_error_in_header" || clueType == "c_syntax_error_in_source"
}

func (p *CSyntaxErrorPlanner) Plan(clues []*pipeline.ErrorClue, gitState *pipeline.GitState) ([]*pipeline.RepairPlan, error) {
	var plans []*pipeline.RepairPlan
	for _, clue := range clues {
		if !p.CanHandle(clue.ClueType) {
			continue
		}

		filePath := clue.Context["file_path"]
		if filePath == "" {
			continue
		}

		// Restore the file with syntax error
		plans = append(plans, &pipeline.RepairPlan{
			PlanType:   "restore_file",
			Priority:   0,
			TargetFile: filePath,
			Action:     "restore_full",
			Params:     map[string]interface{}{"ref": gitState.Ref},
			Reason:     fmt.Sprintf("Restore %s (syntax error)", filePath),
			ClueSource: clue,
		})
	}
	return plans, nil
}

// Helper functions

func findFileInDeleted(filename string, deletedFiles []string) string {
	// Exact match first
	for _, deleted := range deletedFiles {
		if deleted == filename {
			return deleted
		}
	}
	// Try with directory prefix
	for _, deleted := range deletedFiles {
		if strings.HasSuffix(deleted, "/"+filename) {
			return deleted
		}
		if filepath.Base(deleted) == filename {
			return deleted
		}
	}
	return ""
}

func matchGlob(pattern string, files []string) []string {
	var matches []string
	for _, f := range files {
		if matched, _ := filepath.Match(pattern, f); matched {
			matches = append(matches, f)
		}
	}
	return matches
}

func fileExists(path string) bool {
	_, err := os.Stat(path)
	return err == nil
}

func getGitFileContent(file, ref string) (string, error) {
	cmd := exec.Command("git", "show", fmt.Sprintf("%s:%s", ref, file))
	output, err := cmd.Output()
	if err != nil {
		return "", err
	}
	return string(output), nil
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

// extractFileReferences reads the test file around the failure line and extracts
// file references from patterns like command=["./dim", "example.c"]
func extractFileReferences(testFile string, lineNumber int, gitState *pipeline.GitState) []string {
	var referencedFiles []string

	// Read the test file content
	content, err := os.ReadFile(testFile)
	if err != nil {
		if pipeline.IsVerbose() {
			fmt.Printf("[extractFileReferences] Error reading file %s: %v\n", testFile, err)
		}
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

	if pipeline.IsVerbose() {
		fmt.Printf("[extractFileReferences] File: %s, lineNumber: %d, lineIdx: %d, range: [%d:%d]\n",
			testFile, lineNumber, lineIdx, startLine, endLine)
	}

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

	if pipeline.IsVerbose() && len(referencedFiles) > 0 {
		fmt.Printf("[extractFileReferences] Found %d file reference(s): %v\n", len(referencedFiles), referencedFiles)
	}

	return referencedFiles
}

// RegisterAllPlanners registers all planners with the global registry
func RegisterAllPlanners() {
	pipeline.RegisterPlanner(NewMissingFilePlanner())
	pipeline.RegisterPlanner(NewMissingDirectoryPlanner())
	pipeline.RegisterPlanner(NewMakeNoRulePlanner())
	pipeline.RegisterPlanner(NewMakeMissingTargetPlanner())
	pipeline.RegisterPlanner(NewPermissionFixPlanner())
	pipeline.RegisterPlanner(NewPythonNameErrorPlanner())
	pipeline.RegisterPlanner(NewTestFailurePlanner())
	pipeline.RegisterPlanner(NewMissingCIncludePlanner())
	pipeline.RegisterPlanner(NewMissingCFunctionPlanner())
	pipeline.RegisterPlanner(NewUnknownTypeNamePlanner())
	pipeline.RegisterPlanner(NewLinkerUndefinedSymbolsPlanner())
	pipeline.RegisterPlanner(NewCSyntaxErrorPlanner())
}

// All executor implementations for the boil pipeline
package executors

import (
	"crypto/sha256"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"

	"github.com/mdonahoe/boiler/src/boil/pipeline"
)

// GitRestoreExecutor executes file restoration from git
type GitRestoreExecutor struct{}

func NewGitRestoreExecutor() *GitRestoreExecutor {
	return &GitRestoreExecutor{}
}

func (e *GitRestoreExecutor) Name() string {
	return "GitRestoreExecutor"
}

func (e *GitRestoreExecutor) CanHandle(action string) bool {
	return action == "restore_full"
}

func (e *GitRestoreExecutor) ValidatePlan(plan *pipeline.RepairPlan) (bool, string) {
	ref := "HEAD"
	if r, ok := plan.Params["ref"].(string); ok && r != "" {
		ref = r
	}
	filePath := plan.TargetFile

	// Check if file exists in git at ref
	gitToplevel, err := getGitToplevel()
	if err != nil {
		return false, fmt.Sprintf("Cannot get git root: %v", err)
	}

	gitRelativePath := resolveGitPath(filePath, gitToplevel)

	// Try to show the file from git
	cmd := exec.Command("git", "show", fmt.Sprintf("%s:%s", ref, gitRelativePath))
	cmd.Dir = gitToplevel
	if err := cmd.Run(); err != nil {
		return false, fmt.Sprintf("File %s not found in git at %s", gitRelativePath, ref)
	}

	return true, ""
}

func (e *GitRestoreExecutor) Execute(plan *pipeline.RepairPlan) (*pipeline.RepairResult, error) {
	ref := "HEAD"
	if r, ok := plan.Params["ref"].(string); ok && r != "" {
		ref = r
	}
	filePath := plan.TargetFile

	gitToplevel, err := getGitToplevel()
	if err != nil {
		return &pipeline.RepairResult{
			Success:        false,
			PlansAttempted: []*pipeline.RepairPlan{plan},
			FilesModified:  []string{},
			ErrorMessage:   fmt.Sprintf("Cannot get git root: %v", err),
		}, nil
	}

	gitRelativePath := resolveGitPath(filePath, gitToplevel)

	// Check if there are actually changes to restore
	if fileExists(filePath) {
		cmd := exec.Command("git", "diff", "--quiet", ref, "--", gitRelativePath)
		cmd.Dir = gitToplevel
		if err := cmd.Run(); err == nil {
			// File already matches git version
			return &pipeline.RepairResult{
				Success:        false,
				PlansAttempted: []*pipeline.RepairPlan{plan},
				FilesModified:  []string{},
				ErrorMessage:   fmt.Sprintf("File %s already matches git version at %s", filePath, ref),
			}, nil
		}
	}

	// Create parent directories if needed
	parentDir := filepath.Dir(filepath.Join(gitToplevel, gitRelativePath))
	if parentDir != "" {
		os.MkdirAll(parentDir, 0755)
	}

	// Perform git checkout
	cmd := exec.Command("git", "-C", gitToplevel, "checkout", ref, "--", gitRelativePath)
	output, err := cmd.CombinedOutput()
	if err != nil {
		return &pipeline.RepairResult{
			Success:        false,
			PlansAttempted: []*pipeline.RepairPlan{plan},
			FilesModified:  []string{},
			ErrorMessage:   fmt.Sprintf("git checkout failed: %s", string(output)),
		}, nil
	}

	// Verify file exists after checkout
	restoredPath := filepath.Join(gitToplevel, gitRelativePath)
	if !fileExists(restoredPath) {
		return &pipeline.RepairResult{
			Success:        false,
			PlansAttempted: []*pipeline.RepairPlan{plan},
			FilesModified:  []string{},
			ErrorMessage:   fmt.Sprintf("File %s does not exist after git checkout", gitRelativePath),
		}, nil
	}

	// Verify something actually changed
	cmd = exec.Command("git", "diff", "--quiet", "boiling", "--", gitRelativePath)
	cmd.Dir = gitToplevel
	if err := cmd.Run(); err == nil {
		// No difference from boiling branch
		return &pipeline.RepairResult{
			Success:        false,
			PlansAttempted: []*pipeline.RepairPlan{plan},
			FilesModified:  []string{},
			ErrorMessage:   fmt.Sprintf("Restoring %s did not create any changes", filePath),
		}, nil
	}

	return &pipeline.RepairResult{
		Success:        true,
		PlansAttempted: []*pipeline.RepairPlan{plan},
		FilesModified:  []string{gitRelativePath},
		ErrorMessage:   "",
	}, nil
}

// PythonCodeRestoreExecutor executes Python code restoration using src_repair
type PythonCodeRestoreExecutor struct{}

func NewPythonCodeRestoreExecutor() *PythonCodeRestoreExecutor {
	return &PythonCodeRestoreExecutor{}
}

func (e *PythonCodeRestoreExecutor) Name() string {
	return "PythonCodeRestoreExecutor"
}

func (e *PythonCodeRestoreExecutor) CanHandle(action string) bool {
	return action == "restore_python_element"
}

func (e *PythonCodeRestoreExecutor) ValidatePlan(plan *pipeline.RepairPlan) (bool, string) {
	elementName, ok := plan.Params["element_name"].(string)
	if !ok || elementName == "" {
		return false, "element_name parameter is required"
	}

	if !fileExists(plan.TargetFile) {
		return false, fmt.Sprintf("File %s does not exist", plan.TargetFile)
	}

	return true, ""
}

func (e *PythonCodeRestoreExecutor) Execute(plan *pipeline.RepairPlan) (*pipeline.RepairResult, error) {
	filePath := plan.TargetFile
	elementName := plan.Params["element_name"].(string)
	ref := "HEAD"
	if r, ok := plan.Params["ref"].(string); ok && r != "" {
		ref = r
	}

	gitToplevel, err := getGitToplevel()
	if err != nil {
		return &pipeline.RepairResult{
			Success:        false,
			PlansAttempted: []*pipeline.RepairPlan{plan},
			FilesModified:  []string{},
			ErrorMessage:   fmt.Sprintf("Cannot get git root: %v", err),
		}, nil
	}

	// Shell out to Python to use src_repair
	pythonCode := fmt.Sprintf(`
import sys
sys.path.insert(0, %q)
from src.tools.src_repair import repair
repair(%q, %q, missing=%q, verbose=False)
`, gitToplevel, filePath, ref, elementName)

	cmd := exec.Command("python3", "-c", pythonCode)
	cmd.Dir = gitToplevel
	output, err := cmd.CombinedOutput()
	if err != nil {
		return &pipeline.RepairResult{
			Success:        false,
			PlansAttempted: []*pipeline.RepairPlan{plan},
			FilesModified:  []string{},
			ErrorMessage:   fmt.Sprintf("Python src_repair failed: %s\n%s", err, string(output)),
		}, nil
	}

	absPath, _ := filepath.Abs(filePath)
	gitRelativePath, _ := filepath.Rel(gitToplevel, absPath)

	return &pipeline.RepairResult{
		Success:        true,
		PlansAttempted: []*pipeline.RepairPlan{plan},
		FilesModified:  []string{gitRelativePath},
		ErrorMessage:   "",
	}, nil
}

// CCodeRestoreExecutor executes C code restoration using src_repair
type CCodeRestoreExecutor struct{}

func NewCCodeRestoreExecutor() *CCodeRestoreExecutor {
	return &CCodeRestoreExecutor{}
}

func (e *CCodeRestoreExecutor) Name() string {
	return "CCodeRestoreExecutor"
}

func (e *CCodeRestoreExecutor) CanHandle(action string) bool {
	return action == "restore_c_element"
}

func (e *CCodeRestoreExecutor) ValidatePlan(plan *pipeline.RepairPlan) (bool, string) {
	elementName, ok := plan.Params["element_name"].(string)
	if !ok || elementName == "" {
		return false, "element_name parameter is required"
	}

	if !fileExists(plan.TargetFile) {
		return false, fmt.Sprintf("File %s does not exist", plan.TargetFile)
	}

	return true, ""
}

func (e *CCodeRestoreExecutor) Execute(plan *pipeline.RepairPlan) (*pipeline.RepairResult, error) {
	filePath := plan.TargetFile
	elementName := plan.Params["element_name"].(string)
	elementType := "function"
	if t, ok := plan.Params["element_type"].(string); ok && t != "" {
		elementType = t
	}
	ref := "HEAD"
	if r, ok := plan.Params["ref"].(string); ok && r != "" {
		ref = r
	}

	gitToplevel, err := getGitToplevel()
	if err != nil {
		return &pipeline.RepairResult{
			Success:        false,
			PlansAttempted: []*pipeline.RepairPlan{plan},
			FilesModified:  []string{},
			ErrorMessage:   fmt.Sprintf("Cannot get git root: %v", err),
		}, nil
	}

	// Capture file state before repair
	beforeHash, _ := fileHash(filePath)

	// Format missing element pattern for src_repair
	missingPattern := elementName
	if elementType == "include" {
		missingPattern = fmt.Sprintf("include:%s", elementName)
	}

	// Shell out to Python to use src_repair
	pythonCode := fmt.Sprintf(`
import sys
sys.path.insert(0, %q)
from src.tools.src_repair import repair
repair(%q, %q, missing=%q, verbose=False)
`, gitToplevel, filePath, ref, missingPattern)

	cmd := exec.Command("python3", "-c", pythonCode)
	cmd.Dir = gitToplevel
	output, err := cmd.CombinedOutput()
	if err != nil {
		return &pipeline.RepairResult{
			Success:        false,
			PlansAttempted: []*pipeline.RepairPlan{plan},
			FilesModified:  []string{},
			ErrorMessage:   fmt.Sprintf("Python src_repair failed: %s\n%s", err, string(output)),
		}, nil
	}

	// Verify file actually changed
	afterHash, _ := fileHash(filePath)
	if beforeHash == afterHash {
		return &pipeline.RepairResult{
			Success:        false,
			PlansAttempted: []*pipeline.RepairPlan{plan},
			FilesModified:  []string{},
			ErrorMessage:   fmt.Sprintf("Repair did not modify %s", filePath),
		}, nil
	}

	absPath, _ := filepath.Abs(filePath)
	gitRelativePath, _ := filepath.Rel(gitToplevel, absPath)

	return &pipeline.RepairResult{
		Success:        true,
		PlansAttempted: []*pipeline.RepairPlan{plan},
		FilesModified:  []string{gitRelativePath},
		ErrorMessage:   "",
	}, nil
}

// Helper functions

func getGitToplevel() (string, error) {
	cmd := exec.Command("git", "rev-parse", "--show-toplevel")
	output, err := cmd.Output()
	if err != nil {
		return "", err
	}
	return strings.TrimSpace(string(output)), nil
}

func resolveGitPath(filePath, gitToplevel string) string {
	// If path is absolute, make it relative to git root
	if filepath.IsAbs(filePath) {
		rel, err := filepath.Rel(gitToplevel, filePath)
		if err == nil {
			return rel
		}
	}

	// Check if the path exists when interpreted as git-root-relative
	gitRootPath := filepath.Join(gitToplevel, filePath)
	if fileExists(gitRootPath) || strings.Contains(filePath, "/") {
		return filePath
	}

	// Otherwise, treat as cwd-relative
	absPath, _ := filepath.Abs(filePath)
	rel, _ := filepath.Rel(gitToplevel, absPath)
	return rel
}

func fileExists(path string) bool {
	_, err := os.Stat(path)
	return err == nil
}

func fileHash(path string) (string, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return "", err
	}
	hash := sha256.Sum256(data)
	return fmt.Sprintf("%x", hash), nil
}

// RegisterAllExecutors registers all executors with the global registry
func RegisterAllExecutors() {
	pipeline.RegisterExecutor(NewGitRestoreExecutor())
	pipeline.RegisterExecutor(NewPythonCodeRestoreExecutor())
	pipeline.RegisterExecutor(NewCCodeRestoreExecutor())
}

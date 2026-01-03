// Git operations for the boiling system
package core

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"sort"
	"strings"

	"github.com/mdonahoe/boiler/src/boil/pipeline"
)

const BoilingBranch = "boiling"

// GetGitDir returns the .git directory path
func GetGitDir() (string, error) {
	out, err := exec.Command("git", "rev-parse", "--git-dir").Output()
	if err != nil {
		return "", err
	}
	return strings.TrimSpace(string(out)), nil
}

// GetGitToplevel returns the git repository root directory
func GetGitToplevel() (string, error) {
	out, err := exec.Command("git", "rev-parse", "--show-toplevel").Output()
	if err != nil {
		return "", err
	}
	return strings.TrimSpace(string(out)), nil
}

// GetDeletedFiles returns a sorted list of deleted files
func GetDeletedFiles(ref string) ([]string, error) {
	result, err := exec.Command("git", "diff", "--name-status", ref).Output()
	if err != nil {
		return nil, err
	}

	var deleted []string
	lines := strings.Split(string(result), "\n")
	for _, line := range lines {
		if strings.HasPrefix(line, "D\t") || strings.HasPrefix(line, "D ") {
			parts := strings.Fields(line)
			if len(parts) >= 2 {
				deleted = append(deleted, parts[1])
			}
		}
	}

	sort.Strings(deleted) // Sort for deterministic iteration
	return deleted, nil
}

// GitCheckout checks out a file from git
func GitCheckout(filePath string, ref string) (bool, error) {
	deletedFiles, err := GetDeletedFiles(ref)
	if err != nil {
		return false, err
	}

	// Check if file is in deleted files
	found := false
	for _, f := range deletedFiles {
		if f == filePath {
			found = true
			break
		}
	}

	if !found {
		fmt.Printf("missing: %s\n", filePath)
		return false, nil
	}

	// Get paths
	gitToplevel, err := GetGitToplevel()
	if err != nil {
		return false, err
	}

	cwd, err := os.Getwd()
	if err != nil {
		return false, err
	}

	absPath := filepath.Join(gitToplevel, filePath)
	cwdRelativePath, err := filepath.Rel(cwd, absPath)
	if err != nil {
		return false, err
	}

	// For Python files, create empty file first
	if strings.HasSuffix(filePath, ".py") {
		fmt.Printf("creating empty Python file: %s\n", cwdRelativePath)
		// Create parent directories if needed
		dir := filepath.Dir(cwdRelativePath)
		if dir != "" && dir != "." {
			if err := os.MkdirAll(dir, 0755); err != nil {
				return false, err
			}
		}
		// Create empty Python file
		if err := os.WriteFile(cwdRelativePath, []byte(""), 0644); err != nil {
			return false, err
		}
		return true, nil
	}

	// For non-Python files, do full checkout from git root
	stdout, stderr, exitCode := RunCommand([]string{"git", "-C", gitToplevel, "checkout", ref, "--", filePath})
	if exitCode != 0 {
		fmt.Printf("stdout: %s\n", stdout)
		fmt.Printf("stderr: %s\n", stderr)
		return false, fmt.Errorf("git checkout failed for %s", filePath)
	}

	_, err = os.Stat(cwdRelativePath)
	success := err == nil
	fmt.Printf("success = %v\n", success)
	return success, nil
}

// GetTrackedFiles returns all tracked files in the repository
func GetTrackedFiles() ([]string, error) {
	result, err := exec.Command("git", "ls-files").Output()
	if err != nil {
		return []string{}, nil
	}

	output := strings.TrimSpace(string(result))
	if output == "" {
		return []string{}, nil
	}

	files := strings.Split(output, "\n")
	return files, nil
}

// GitResetHard resets the repository to a specific commit with --hard
func GitResetHard(commit string) error {
	return exec.Command("git", "reset", "--hard", commit).Run()
}

// GetGitFileInfo gets information about modified and deleted files
func GetGitFileInfo(ref string) (*GitFileInfo, error) {
	gitDir, err := GetGitDir()
	if err != nil {
		return nil, err
	}

	indexFile := filepath.Join(gitDir, "boil.index")
	env := append(os.Environ(), "GIT_INDEX_FILE="+indexFile)

	var partialFiles []*pipeline.PartialFileInfo
	var deletedFiles []string

	// Get list of modified and deleted files
	cmd := exec.Command("git", "diff", "--name-status", ref)
	cmd.Env = env
	result, err := cmd.Output()
	if err != nil {
		// If git diff fails, return empty lists
		return &GitFileInfo{
			PartialFiles:  partialFiles,
			DeletedFiles:  deletedFiles,
			GitToplevel:   "",
		}, nil
	}

	gitToplevel, _ := GetGitToplevel()

	lines := strings.Split(strings.TrimSpace(string(result)), "\n")
	for _, line := range lines {
		if line == "" {
			continue
		}
		parts := strings.Fields(line)
		if len(parts) < 2 {
			continue
		}

		status, filePath := parts[0], parts[1]

		if status == "D" {
			deletedFiles = append(deletedFiles, filePath)
		} else if status == "M" {
			// Count lines in modified file
			currentLines := 0
			totalLines := 0

			// Get current line count
			data, err := os.ReadFile(filePath)
			if err == nil {
				currentLines = len(strings.Split(string(data), "\n"))
			}

			// Get total line count from git at the ref
			gitCmd := exec.Command("git", "show", fmt.Sprintf("%s:%s", ref, filePath))
			gitOutput, err := gitCmd.Output()
			if err == nil {
				totalLines = len(strings.Split(string(gitOutput), "\n"))
			}

			lineRatio := fmt.Sprintf("%d/%d", currentLines, totalLines)
			if err != nil {
				lineRatio = "unknown"
			}

			partialFiles = append(partialFiles, &pipeline.PartialFileInfo{
				File:      filePath,
				LineRatio: lineRatio,
				Status:    status,
			})
		}
	}

	return &GitFileInfo{
		PartialFiles:  partialFiles,
		DeletedFiles:  deletedFiles,
		GitToplevel:   gitToplevel,
	}, nil
}

// GitFileInfo holds git file information
type GitFileInfo struct {
	PartialFiles  []*pipeline.PartialFileInfo
	DeletedFiles  []string
	GitToplevel   string
}

// SaveChanges commits the current working directory relative to a parent
// Returns the created commit hash
func SaveChanges(parent, message, branchName string) (string, error) {
	gitDir, err := GetGitDir()
	if err != nil {
		return "", err
	}

	// Copy .git/index to .git/boil.index
	indexFile := filepath.Join(gitDir, "index")
	boilIndexFile := filepath.Join(gitDir, "boil.index")

	input, err := os.ReadFile(indexFile)
	if err != nil {
		return "", err
	}
	if err := os.WriteFile(boilIndexFile, input, 0644); err != nil {
		return "", err
	}

	// Set GIT_INDEX_FILE for all git commands
	env := append(os.Environ(), "GIT_INDEX_FILE="+boilIndexFile)

	// Add .boil directory if it exists
	if info, err := os.Stat(".boil"); err == nil && info.IsDir() {
		cmd := exec.Command("git", "add", ".boil")
		cmd.Env = env
		if err := cmd.Run(); err != nil {
			return "", err
		}
	}

	// Add updated files
	cmd := exec.Command("git", "add", "-u")
	cmd.Env = env
	if err := cmd.Run(); err != nil {
		return "", err
	}

	// Write tree
	cmd = exec.Command("git", "write-tree")
	cmd.Env = env
	out, err := cmd.Output()
	if err != nil {
		return "", err
	}
	tree := strings.TrimSpace(string(out))

	// Commit tree
	cmd = exec.Command("git", "commit-tree", tree, "-p", parent, "-m", message)
	cmd.Env = env
	out, err = cmd.Output()
	if err != nil {
		return "", err
	}
	commit := strings.TrimSpace(string(out))

	// Update branch ref if specified
	if branchName != "" {
		cmd = exec.Command("git", "update-ref", "refs/heads/"+branchName, commit)
		if err := cmd.Run(); err != nil {
			return "", err
		}
	}

	return commit, nil
}

// GetUncommittedChanges returns files with uncommitted changes that would be lost by boiling:
// - Untracked files (not in git at all)
// - Modified files (tracked files with unstaged changes)
// - Staged changes (any staged but uncommitted changes)
// All of these contain "new code" that doesn't exist in git history and can't be restored.
func GetUncommittedChanges() ([]string, error) {
	var changes []string

	// Get untracked files (excluding .boil directory and build artifacts)
	cmd := exec.Command("git", "ls-files", "--others", "--exclude-standard")
	out, err := cmd.Output()
	if err != nil {
		return nil, err
	}
	for _, line := range strings.Split(strings.TrimSpace(string(out)), "\n") {
		if line != "" && !isBuildArtifact(line) {
			changes = append(changes, line+" (untracked)")
		}
	}

	// Get unstaged modifications that ADD lines (not just deletions)
	// Use --numstat to see lines added vs removed
	cmd = exec.Command("git", "diff", "--numstat")
	out, err = cmd.Output()
	if err != nil {
		return changes, nil
	}
	for _, line := range strings.Split(strings.TrimSpace(string(out)), "\n") {
		if line == "" {
			continue
		}
		parts := strings.Fields(line)
		if len(parts) >= 3 {
			added := parts[0]
			// parts[1] is removed
			filePath := parts[2]
			// Only report if lines were ADDED (not just removed)
			// Deletions are OK because the content is tracked in git
			if added != "0" && added != "-" && !isBuildArtifact(filePath) {
				changes = append(changes, filePath+" (modified)")
			}
		}
	}

	// Get staged new files (A status)
	cmd = exec.Command("git", "diff", "--cached", "--name-status", "HEAD")
	out, err = cmd.Output()
	if err != nil {
		// If HEAD doesn't exist (empty repo), try without HEAD
		cmd = exec.Command("git", "diff", "--cached", "--name-status")
		out, err = cmd.Output()
		if err != nil {
			return changes, nil
		}
	}
	for _, line := range strings.Split(strings.TrimSpace(string(out)), "\n") {
		if line == "" {
			continue
		}
		parts := strings.Fields(line)
		if len(parts) >= 2 {
			status := parts[0]
			filePath := parts[1]
			if status == "A" && !isBuildArtifact(filePath) {
				changes = append(changes, filePath+" (staged new file)")
			}
			// D (deletions) are OK - they're tracked in git already
			// M (modifications) handled below with numstat
		}
	}

	// Get staged modifications that ADD lines (not just deletions)
	cmd = exec.Command("git", "diff", "--cached", "--numstat", "HEAD")
	out, err = cmd.Output()
	if err != nil {
		cmd = exec.Command("git", "diff", "--cached", "--numstat")
		out, err = cmd.Output()
		if err != nil {
			return changes, nil
		}
	}
	for _, line := range strings.Split(strings.TrimSpace(string(out)), "\n") {
		if line == "" {
			continue
		}
		parts := strings.Fields(line)
		if len(parts) >= 3 {
			added := parts[0]
			filePath := parts[2]
			// Only report if lines were ADDED (not just removed)
			if added != "0" && added != "-" && !isBuildArtifact(filePath) {
				// Check if this is a new file (already reported above)
				isNewFile := false
				checkCmd := exec.Command("git", "diff", "--cached", "--name-status", "HEAD", "--", filePath)
				if checkOut, err := checkCmd.Output(); err == nil {
					if strings.HasPrefix(strings.TrimSpace(string(checkOut)), "A") {
						isNewFile = true
					}
				}
				if !isNewFile {
					changes = append(changes, filePath+" (staged modification)")
				}
			}
		}
	}

	return changes, nil
}

// isBuildArtifact returns true if the file is likely a build artifact
// that doesn't need protection from being lost.
func isBuildArtifact(path string) bool {
	// .boil directory
	if strings.HasPrefix(path, ".boil/") || path == ".boil" {
		return true
	}

	// Python bytecode cache
	if strings.Contains(path, "__pycache__/") || strings.HasSuffix(path, ".pyc") || strings.HasSuffix(path, ".pyo") {
		return true
	}

	// Object files
	if strings.HasSuffix(path, ".o") || strings.HasSuffix(path, ".obj") {
		return true
	}

	// Common compiled/build outputs (no extension in root directory)
	// Check if corresponding source file exists in git history
	base := filepath.Base(path)
	dir := filepath.Dir(path)
	if !strings.Contains(base, ".") && (dir == "." || dir == "") {
		// File has no extension and is in root - check for source file in git
		sourceExts := []string{".c", ".go", ".rs", ".cpp", ".cc"}
		for _, ext := range sourceExts {
			// Check if source exists in working dir
			if _, err := os.Stat(path + ext); err == nil {
				return true
			}
			// Check if source exists in git history
			cmd := exec.Command("git", "ls-files", path+ext)
			if out, err := cmd.Output(); err == nil && strings.TrimSpace(string(out)) != "" {
				return true // Has corresponding source file in git, likely compiled binary
			}
		}
	}

	return false
}

// HasChanges checks if there are uncommitted changes
func HasChanges() (bool, error) {
	gitDir, err := GetGitDir()
	if err != nil {
		return false, err
	}

	boilIndexFile := filepath.Join(gitDir, "boil.index")
	env := append(os.Environ(), "GIT_INDEX_FILE="+boilIndexFile)

	// Check for modified files
	cmd := exec.Command("git", "diff", "--quiet", BoilingBranch)
	cmd.Env = env
	err = cmd.Run()
	modified := err != nil // Exit code != 0 means changes exist

	// Check for untracked files
	cmd = exec.Command("git", "ls-files", "--others", "--exclude-standard")
	cmd.Env = env
	out, err := cmd.Output()
	if err != nil {
		return false, err
	}

	untracked := false
	lines := strings.Split(string(out), "\n")
	for _, line := range lines {
		if line != "" && !strings.Contains(line, ".boil") {
			untracked = true
			break
		}
	}

	return modified || untracked, nil
}

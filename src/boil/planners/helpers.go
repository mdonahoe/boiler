// Common helper functions used by multiple planners
package planners

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
)

// findFileInDeleted looks for a file in the list of deleted files
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

// matchGlob returns files matching a glob pattern
func matchGlob(pattern string, files []string) []string {
	var matches []string
	for _, f := range files {
		if matched, _ := filepath.Match(pattern, f); matched {
			matches = append(matches, f)
		}
	}
	return matches
}

// fileExists checks if a file exists
func fileExists(path string) bool {
	_, err := os.Stat(path)
	return err == nil
}

// getGitFileContent retrieves file content from git at a specific ref
func getGitFileContent(file, ref string) (string, error) {
	cmd := exec.Command("git", "show", fmt.Sprintf("%s:%s", ref, file))
	output, err := cmd.Output()
	if err != nil {
		return "", err
	}
	return string(output), nil
}

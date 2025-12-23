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

// containsFunctionDefinition checks if a C file contains a function definition
// (not just a call) for the given symbol. Function definitions in C look like:
//   ReturnType function_name(params) {
// while function calls look like:
//   result = function_name(args);
func containsFunctionDefinition(content, symbol string) bool {
	lines := strings.Split(content, "\n")
	for i, line := range lines {
		// Skip lines that look like function calls (have = before the symbol)
		eqIdx := strings.Index(line, "=")
		symIdx := strings.Index(line, symbol)
		if symIdx == -1 {
			continue
		}
		// If there's an = before the symbol on the same line, it's likely a call
		if eqIdx != -1 && eqIdx < symIdx {
			continue
		}
		// Check if symbol is followed by ( - could be definition or call
		afterSym := line[symIdx+len(symbol):]
		if !strings.HasPrefix(strings.TrimSpace(afterSym), "(") {
			continue
		}
		// Look for { on this line or the next few lines (function definition)
		// Function definitions have { after the parameter list
		for j := i; j < len(lines) && j < i+5; j++ {
			checkLine := lines[j]
			if strings.Contains(checkLine, "{") {
				// Make sure it's not inside a string or comment
				// Simple check: { appears and it's likely a function body start
				return true
			}
			// If we hit a semicolon, it's a declaration or call, not definition
			if strings.Contains(checkLine, ";") && j > i {
				break
			}
		}
	}
	return false
}

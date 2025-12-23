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

// containsSymbolDefinition checks if a C file contains a definition (not just
// a usage) for the given symbol. This handles both:
//   1. Function definitions: ReturnType symbol(params) {
//   2. Global variable definitions: Type symbol = value; or Type (*symbol)(...) = value;
func containsSymbolDefinition(content, symbol string) bool {
	lines := strings.Split(content, "\n")
	for i, line := range lines {
		symIdx := strings.Index(line, symbol)
		if symIdx == -1 {
			continue
		}

		// Make sure it's a word boundary (not part of another identifier)
		if symIdx > 0 {
			prevChar := line[symIdx-1]
			if (prevChar >= 'a' && prevChar <= 'z') || (prevChar >= 'A' && prevChar <= 'Z') || prevChar == '_' {
				continue
			}
		}
		if symIdx+len(symbol) < len(line) {
			nextChar := line[symIdx+len(symbol)]
			// Allow ( for functions, ) for function pointers like (*symbol), and space/= for variables
			if (nextChar >= 'a' && nextChar <= 'z') || (nextChar >= 'A' && nextChar <= 'Z') || nextChar == '_' {
				continue
			}
		}

		eqIdx := strings.Index(line, "=")

		// Case 1: = appears AFTER the symbol - likely a variable/function pointer definition
		// e.g., "void *(*ts_current_malloc)(size_t) = ts_malloc_default;"
		if eqIdx != -1 && eqIdx > symIdx {
			return true
		}

		// Case 2: = appears BEFORE the symbol - likely a function call assignment, skip
		if eqIdx != -1 && eqIdx < symIdx {
			continue
		}

		// Case 3: No = on line, check if it's a function definition
		afterSym := line[symIdx+len(symbol):]
		trimmed := strings.TrimSpace(afterSym)
		if strings.HasPrefix(trimmed, "(") {
			// Look for { on this line or the next few lines (function definition)
			for j := i; j < len(lines) && j < i+5; j++ {
				checkLine := lines[j]
				if strings.Contains(checkLine, "{") {
					return true
				}
				// If we hit a semicolon on a later line, it's a declaration, not definition
				if strings.Contains(checkLine, ";") && j > i {
					break
				}
			}
		}
	}
	return false
}

// containsFunctionDefinition is an alias for containsSymbolDefinition for backwards compatibility
func containsFunctionDefinition(content, symbol string) bool {
	return containsSymbolDefinition(content, symbol)
}

// findMatchingDirectoryPath finds a directory path in deleted files that matches
// a suffix of the given absolute path. This handles cases where the error message
// contains an absolute path from a different working directory than the git root.
// For example, if absPath is "/root/boiler/example_repos/dim/before" and deleted
// files include "example_repos/dim/before/Makefile", this returns "example_repos/dim/before".
func findMatchingDirectoryPath(absPath string, deletedFiles []string) string {
	// Clean the path and split into components
	absPath = filepath.Clean(absPath)
	parts := strings.Split(absPath, string(filepath.Separator))

	// Try progressively shorter suffixes of the path
	for i := 0; i < len(parts); i++ {
		suffix := filepath.Join(parts[i:]...)
		if suffix == "" {
			continue
		}
		// Check if any deleted file starts with this suffix + /
		for _, deleted := range deletedFiles {
			if strings.HasPrefix(deleted, suffix+"/") {
				return suffix
			}
		}
	}
	return ""
}

// findMatchingFilePath finds a file path in deleted files that matches
// a suffix of the given absolute path. This handles cases where the error message
// contains an absolute path from a different working directory than the git root.
func findMatchingFilePath(absPath string, deletedFiles []string) string {
	// Clean the path and split into components
	absPath = filepath.Clean(absPath)
	parts := strings.Split(absPath, string(filepath.Separator))

	// Try progressively shorter suffixes of the path
	for i := 0; i < len(parts); i++ {
		suffix := filepath.Join(parts[i:]...)
		if suffix == "" {
			continue
		}
		// Check for exact match
		for _, deleted := range deletedFiles {
			if deleted == suffix {
				return suffix
			}
		}
	}
	return ""
}

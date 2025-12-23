// repair.go provides source code repair functionality
// This is a Go port of src_repair.py
package ast

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"strings"
)

// patternMatch checks if any pattern matches any label
func patternMatch(patterns map[string]bool, labels []Annotation) (string, string, bool) {
	for _, label := range labels {
		labelStr := label.String()
		for pattern := range patterns {
			matched, err := regexp.MatchString(pattern, labelStr)
			if err == nil && matched {
				return pattern, labelStr, true
			}
		}
	}
	return "", "", false
}

// getCodes returns the on-disk code and git version of a file
func getCodes(filename, commit string) (string, string, error) {
	// Get relative path for git
	cwd, err := os.Getwd()
	if err != nil {
		return "", "", err
	}
	repoPath, err := filepath.Rel(cwd, filename)
	if err != nil {
		repoPath = filename
	}

	// Read on-disk code
	var indexCode string
	if _, err := os.Stat(filename); os.IsNotExist(err) {
		// File doesn't exist, restore from git and clear
		cmd := exec.Command("git", "checkout", repoPath)
		if err := cmd.Run(); err != nil {
			return "", "", fmt.Errorf("failed to restore %s: %w", repoPath, err)
		}
		// Clear it
		if err := os.WriteFile(filename, []byte{}, 0644); err != nil {
			return "", "", err
		}
		indexCode = ""
	} else if err != nil {
		return "", "", err
	} else {
		data, err := os.ReadFile(filename)
		if err != nil {
			return "", "", err
		}
		indexCode = string(data)
	}

	// Get git version
	cmd := exec.Command("git", "show", fmt.Sprintf("%s:%s", commit, repoPath))
	output, err := cmd.Output()
	if err != nil {
		return "", "", fmt.Errorf("failed to get git version of %s: %w", filename, err)
	}
	gitCode := string(output)

	return indexCode, gitCode, nil
}

// filterCode removes lines from code that don't match syntactic patterns
func filterCode(code string, patterns map[string]bool, lang Language, verbose bool) ([]string, error) {
	annotations, err := GetAnnotations([]byte(code), lang)
	if err != nil {
		return nil, err
	}

	lines := strings.Split(code, "\n")
	var result []string

	for lineno, line := range lines {
		include := true
		var matchInfo string

		if lineno < len(annotations) {
			labels := annotations[lineno]
			if len(labels) == 0 {
				// Include any line without tags
				include = true
				matchInfo = "no labels"
			} else {
				pattern, label, matched := patternMatch(patterns, labels)
				include = matched
				if matched {
					matchInfo = fmt.Sprintf("matched %s = %s", pattern, label)
				} else {
					matchInfo = fmt.Sprintf("no match for %v", labels)
				}
			}
		}

		if verbose {
			marker := "+"
			if !include {
				marker = "-"
			}
			fmt.Printf(" %s %d: %s -> %s\n", marker, lineno+1, matchInfo, line)
		}

		if include {
			result = append(result, line)
		}
	}

	return result, nil
}

// Repair restores deleted lines to a file that match the missing pattern
func Repair(filename, commit string, missing string, verbose bool) error {
	lang, err := InferLanguage(filename)
	if err != nil {
		return err
	}

	if verbose {
		fmt.Printf("repairing %s from %s missing %s\n", filename, commit, missing)
	}

	indexCode, gitCode, err := getCodes(filename, commit)
	if err != nil {
		return err
	}

	// Get labels from the current on-disk code
	labels, err := GetLabels([]byte(indexCode), lang)
	if err != nil {
		return err
	}

	// Build allowed patterns (exclude decorators)
	allowedPatterns := make(map[string]bool)
	for label := range labels {
		if !strings.HasPrefix(label, "decorator:") {
			allowedPatterns[label] = true
		}
	}

	// Add the missing pattern
	if missing != "" {
		if !strings.Contains(missing, ":") {
			// Assume this is just a name, match types that introduce names
			switch lang {
			case LangPython:
				missing = "(class|function|import|alias):" + missing
			case LangC:
				missing = "(function|include):" + missing
			}
		}
		allowedPatterns[missing] = true
	}

	// Filter git code using the allowed patterns
	lines, err := filterCode(gitCode, allowedPatterns, lang, verbose)
	if err != nil {
		return err
	}

	// Write filtered code to file
	content := strings.Join(lines, "\n")
	if !strings.HasSuffix(content, "\n") && len(lines) > 0 {
		content += "\n"
	}
	return os.WriteFile(filename, []byte(content), 0644)
}

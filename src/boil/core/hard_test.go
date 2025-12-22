package core

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"

	"github.com/mdonahoe/boiler/src/boil/handlers"
)

// TestBoilHardDim tests the --hard mode on the dim example repo.
// On failure, writes a detailed report to /tmp/boil_hard_fail.txt
func TestBoilHardDim(t *testing.T) {
	// Skip if SKIP_SLOW_TESTS is set
	if os.Getenv("SKIP_SLOW_TESTS") == "1" {
		t.Skip("Slow test skipped")
	}

	// Register handlers
	if err := handlers.RegisterAllHandlers(); err != nil {
		t.Fatalf("Failed to register handlers: %v", err)
	}

	// Find the boiler root directory
	boilerDir := findBoilerDir(t)

	// Build the boil binary
	boilBinary := filepath.Join(boilerDir, "boil")
	buildCmd := exec.Command("go", "build", "-o", boilBinary, ".")
	buildCmd.Dir = filepath.Join(boilerDir, "src", "boil")
	if out, err := buildCmd.CombinedOutput(); err != nil {
		t.Fatalf("Failed to build boil binary: %v\n%s", err, out)
	}

	// Create a temporary directory
	tmpDir, err := os.MkdirTemp("", "boil_hard_test_*")
	if err != nil {
		t.Fatalf("Failed to create temp dir: %v", err)
	}
	defer os.RemoveAll(tmpDir)

	// Copy files from example_repos/dim/before
	srcDir := filepath.Join(boilerDir, "example_repos", "dim", "before")
	if err := copyDir(srcDir, tmpDir); err != nil {
		t.Fatalf("Failed to copy dim/before: %v", err)
	}

	// Initialize git repo
	if err := runCmd(tmpDir, "git", "init"); err != nil {
		t.Fatalf("Failed to git init: %v", err)
	}
	if err := runCmd(tmpDir, "git", "config", "user.email", "test@test.com"); err != nil {
		t.Fatalf("Failed to set git email: %v", err)
	}
	if err := runCmd(tmpDir, "git", "config", "user.name", "Test"); err != nil {
		t.Fatalf("Failed to set git name: %v", err)
	}
	if err := runCmd(tmpDir, "git", "add", "."); err != nil {
		t.Fatalf("Failed to git add: %v", err)
	}
	if err := runCmd(tmpDir, "git", "commit", "-m", "initial"); err != nil {
		t.Fatalf("Failed to git commit: %v", err)
	}

	// Verify make test passes before boiling
	makeTestCmd := exec.Command("make", "test")
	makeTestCmd.Dir = tmpDir
	if out, err := makeTestCmd.CombinedOutput(); err != nil {
		writeFailureReport(t, tmpDir, "pre-boil make test", out, err)
		t.Fatalf("make test failed before boiling: %v", err)
	}

	// Run boil --hard make test
	boilCmd := exec.Command(boilBinary, "--hard", "make", "test")
	boilCmd.Dir = tmpDir
	boilCmd.Env = append(os.Environ(), "BOIL_VERBOSE=0")
	boilOut, boilErr := boilCmd.CombinedOutput()

	if boilErr != nil {
		writeFailureReport(t, tmpDir, "boil --hard make test", boilOut, boilErr)
		t.Fatalf("boil --hard failed: %v\nOutput:\n%s", boilErr, boilOut)
	}

	// Verify make test passes after boiling
	finalTestCmd := exec.Command("make", "test")
	finalTestCmd.Dir = tmpDir
	finalOut, finalErr := finalTestCmd.CombinedOutput()
	if finalErr != nil {
		writeFailureReport(t, tmpDir, "post-boil make test", finalOut, finalErr)
		t.Fatalf("make test failed after boiling: %v\nOutput:\n%s", finalErr, finalOut)
	}

	t.Logf("boil --hard succeeded on dim repo")
}

// findBoilerDir finds the root boiler directory by looking for AGENTS.md
func findBoilerDir(t *testing.T) string {
	t.Helper()

	// Start from current working directory and go up
	dir, err := os.Getwd()
	if err != nil {
		t.Fatalf("Failed to get working directory: %v", err)
	}

	for {
		if _, err := os.Stat(filepath.Join(dir, "AGENTS.md")); err == nil {
			return dir
		}
		parent := filepath.Dir(dir)
		if parent == dir {
			t.Fatalf("Could not find boiler root directory")
		}
		dir = parent
	}
}

// copyDir recursively copies a directory
func copyDir(src, dst string) error {
	return filepath.Walk(src, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}

		// Skip hidden files and directories
		if strings.HasPrefix(info.Name(), ".") && info.Name() != "." {
			if info.IsDir() {
				return filepath.SkipDir
			}
			return nil
		}

		relPath, err := filepath.Rel(src, path)
		if err != nil {
			return err
		}
		dstPath := filepath.Join(dst, relPath)

		if info.IsDir() {
			return os.MkdirAll(dstPath, info.Mode())
		}

		data, err := os.ReadFile(path)
		if err != nil {
			return err
		}
		return os.WriteFile(dstPath, data, info.Mode())
	})
}

// runCmd runs a command in the given directory
func runCmd(dir string, name string, args ...string) error {
	cmd := exec.Command(name, args...)
	cmd.Dir = dir
	out, err := cmd.CombinedOutput()
	if err != nil {
		return fmt.Errorf("%s %v failed: %v\n%s", name, args, err, out)
	}
	return nil
}

// writeFailureReport writes a detailed failure report to /tmp/boil_hard_fail.txt
func writeFailureReport(t *testing.T, tmpDir, stage string, output []byte, err error) {
	t.Helper()

	reportPath := "/tmp/boil_hard_fail.txt"

	var report strings.Builder
	report.WriteString("=" + strings.Repeat("=", 79) + "\n")
	report.WriteString("BOIL --HARD TEST FAILURE REPORT\n")
	report.WriteString("=" + strings.Repeat("=", 79) + "\n\n")

	report.WriteString(fmt.Sprintf("Stage: %s\n", stage))
	report.WriteString(fmt.Sprintf("Error: %v\n", err))
	report.WriteString(fmt.Sprintf("Temp Dir: %s\n\n", tmpDir))

	report.WriteString("-" + strings.Repeat("-", 79) + "\n")
	report.WriteString("Command Output:\n")
	report.WriteString("-" + strings.Repeat("-", 79) + "\n")
	report.WriteString(string(output))
	report.WriteString("\n\n")

	// List files in tmpDir
	report.WriteString("-" + strings.Repeat("-", 79) + "\n")
	report.WriteString("Files in temp directory:\n")
	report.WriteString("-" + strings.Repeat("-", 79) + "\n")
	filepath.Walk(tmpDir, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return nil
		}
		relPath, _ := filepath.Rel(tmpDir, path)
		if info.IsDir() {
			report.WriteString(fmt.Sprintf("[DIR]  %s\n", relPath))
		} else {
			report.WriteString(fmt.Sprintf("[FILE] %s (%d bytes)\n", relPath, info.Size()))
		}
		return nil
	})
	report.WriteString("\n")

	// Check for .boil directory and include debug info
	boilDir := filepath.Join(tmpDir, ".boil")
	if info, err := os.Stat(boilDir); err == nil && info.IsDir() {
		report.WriteString("-" + strings.Repeat("-", 79) + "\n")
		report.WriteString(".boil directory contents:\n")
		report.WriteString("-" + strings.Repeat("-", 79) + "\n")

		// List pipeline JSON files
		files, _ := filepath.Glob(filepath.Join(boilDir, "iter*.pipeline.json"))
		for _, f := range files {
			report.WriteString(fmt.Sprintf("\n--- %s ---\n", filepath.Base(f)))
			content, err := os.ReadFile(f)
			if err == nil {
				// Truncate if too long
				if len(content) > 5000 {
					report.WriteString(string(content[:5000]))
					report.WriteString("\n... (truncated)\n")
				} else {
					report.WriteString(string(content))
				}
			}
		}

		// Include last exit output
		exitFiles, _ := filepath.Glob(filepath.Join(boilDir, "iter*.exit*.txt"))
		if len(exitFiles) > 0 {
			lastExit := exitFiles[len(exitFiles)-1]
			report.WriteString(fmt.Sprintf("\n--- %s ---\n", filepath.Base(lastExit)))
			content, err := os.ReadFile(lastExit)
			if err == nil {
				if len(content) > 3000 {
					report.WriteString(string(content[:3000]))
					report.WriteString("\n... (truncated)\n")
				} else {
					report.WriteString(string(content))
				}
			}
		}
	}

	report.WriteString("\n" + "=" + strings.Repeat("=", 79) + "\n")

	// Write report
	if err := os.WriteFile(reportPath, []byte(report.String()), 0644); err != nil {
		t.Logf("Failed to write failure report: %v", err)
	} else {
		t.Logf("Failure report written to %s", reportPath)
	}
}

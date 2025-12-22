// Main fix loop and CLI command implementations
package core

import (
	"encoding/json"
	"fmt"
	"math/rand"
	"os"
	"os/exec"
	"strconv"
	"strings"
	"time"

	"github.com/mdonahoe/boiler/src/boil/pipeline"
)

// Fix repeatedly runs a command, repairing files until it is fixed
func Fix(command []string, numIterations int, allowLegacy bool) (bool, error) {
	if len(command) == 0 {
		return false, fmt.Errorf("no command provided")
	}

	ref := Ctx().GitRef

	// Check if boiling branch is stale or needs creation
	result := exec.Command("git", "merge-base", "--is-ancestor", ref, BoilingBranch).Run()
	var ancestorCheck int
	if result == nil {
		ancestorCheck = 0
	} else if exitErr, ok := result.(*exec.ExitError); ok {
		ancestorCheck = exitErr.ExitCode()
	} else {
		ancestorCheck = 1
	}

	var action string
	if ancestorCheck == 1 {
		// Existing boiling session is stale
		fmt.Println("existing boiling session is stale. Deleting")
		exec.Command("git", "branch", "-D", BoilingBranch).Run()
		exec.Command("git", "branch", BoilingBranch).Run()
		os.RemoveAll(".boil")
		action = "start"
	} else if ancestorCheck == 128 {
		// Branch doesn't exist
		exec.Command("git", "branch", BoilingBranch).Run()
		action = "start"
	} else if ancestorCheck == 0 {
		// Branch exists and is ancestor of HEAD
		action = "resume"
	} else {
		return false, fmt.Errorf("unexpected ancestor check result: %d", ancestorCheck)
	}

	startCommit := BoilingBranch

	// Save initial state
	boilCommit, err := SaveChanges(
		startCommit,
		fmt.Sprintf("boil_%s\n\n%s", action, strings.Join(command, " ")),
		BoilingBranch,
	)
	if err != nil {
		return false, err
	}

	// Create .boil directory
	os.MkdirAll(".boil", 0755)

	// Count existing iterations
	entries, _ := os.ReadDir(".boil")
	n := 0
	for _, entry := range entries {
		if strings.HasPrefix(entry.Name(), "iter") {
			n++
		}
	}

	// Bootstrap - run command once
	tStart := time.Now()
	stdout, stderr, code := RunCommand(command)
	tRunCommand := time.Since(tStart)

	if code == 0 {
		// Nothing to fix
		return true, nil
	}

	// Main repair loop
	for {
		n++
		fmt.Printf("Attempt %d\n", n)
		fmt.Println(stdout)
		fmt.Println(stderr)

		errOutput := stdout + stderr
		errorFile := fmt.Sprintf(".boil/iter%d.exit%d.txt", n, code)
		if writeErr := os.WriteFile(errorFile, []byte(errOutput), 0644); writeErr != nil {
			return false, writeErr
		}

		message := ""
		exit := false

		// Try pipeline system
		var pipelineResult *pipeline.RepairResult
		if pipeline.HasPipelineHandlers() {
			fmt.Println("[Pipeline] Attempting repair with new pipeline system...")

			// Build git state
			gitInfo, _ := GetGitFileInfo(ref)
			gitState := &pipeline.GitState{
				Ref:          ref,
				DeletedFiles: gitInfo.DeletedFiles,
				GitToplevel:  gitInfo.GitToplevel,
				PartialFiles: gitInfo.PartialFiles,
			}

			// Run pipeline
			pipelineResult, _ = pipeline.RunPipeline(stderr, stdout, gitState, true, true)

			hasChanges, _ := HasChanges()
			if pipelineResult != nil && pipelineResult.Success && hasChanges {
				message = fmt.Sprintf("fixed with pipeline (modified %d file(s))", len(pipelineResult.FilesModified))
				fmt.Printf("[Pipeline] Success: %s\n", message)
			} else {
				fmt.Println("[Pipeline] Pipeline did not produce a fix")
			}
		}

		// Legacy handlers would go here if allowLegacy is true
		// Skipping for now since we're not implementing legacy handlers

		if message == "" {
			message = "failed to handle this type of error"
			exit = true
		}

		// Save debug JSON
		if pipelineResult != nil {
			debugJSONPath := fmt.Sprintf(".boil/iter%d.pipeline.json", n)
			debugData := pipelineResult.ToDict()
			debugData["command"] = strings.Join(command, " ")

			gitInfo, _ := GetGitFileInfo(ref)
			debugData["partial_files"] = gitInfo.PartialFiles
			debugData["deleted_files"] = gitInfo.DeletedFiles
			debugData["command_time"] = tRunCommand.Seconds()

			jsonBytes, _ := json.MarshalIndent(debugData, "", "  ")
			os.WriteFile(debugJSONPath, jsonBytes, 0644)
			fmt.Printf("[Pipeline] Debug info saved to %s\n", debugJSONPath)
		}

		hasChanges, _ := HasChanges()
		if !hasChanges {
			return false, fmt.Errorf("no change")
		}

		// Commit changes
		var commitErr error
		boilCommit, commitErr = SaveChanges(
			boilCommit,
			fmt.Sprintf("boil_%d\n\n%s", n, message),
			BoilingBranch,
		)
		if commitErr != nil {
			return false, commitErr
		}

		if exit {
			return false, fmt.Errorf(message)
		}

		// Re-run command
		tStart = time.Now()
		stdout, stderr, code = RunCommand(command)
		tRunCommand = time.Since(tStart)

		if code == 0 {
			// Success!
			return true, nil
		}

		if numIterations > 0 && n >= numIterations {
			fmt.Printf("Reached iteration limit %d\n", n)
			break
		}
	}

	return false, nil
}

// AbortBoiling aborts current boiling session and restores working directory
func AbortBoiling() int {
	// Check if boiling branch exists
	if err := exec.Command("git", "rev-parse", "--verify", BoilingBranch).Run(); err != nil {
		fmt.Println("No active boiling session found.")
		return 1
	}

	// Find the boil_start commit
	output, err := exec.Command("git", "log", "--format=%H", "--grep", "boil_start", fmt.Sprintf("HEAD..%s", BoilingBranch)).Output()
	if err != nil {
		fmt.Println("Error: Could not find boil_start commit on boiling branch.")
		return 1
	}

	commits := strings.Split(strings.TrimSpace(string(output)), "\n")
	if len(commits) == 0 || commits[0] == "" {
		fmt.Println("Error: Could not find boil_start commit on boiling branch.")
		return 1
	}

	boilStartCommit := commits[0]
	fmt.Printf("Found boil_start commit: %s\n", boilStartCommit)

	// Get the parent of boil_start
	originalCommit, err := exec.Command("git", "rev-parse", fmt.Sprintf("%s^", boilStartCommit)).Output()
	if err != nil {
		fmt.Printf("Error getting parent commit: %v\n", err)
		return 1
	}

	originalCommitStr := strings.TrimSpace(string(originalCommit))
	fmt.Printf("Restoring to original commit: %s\n", originalCommitStr)

	// Reset to the original commit
	if err := GitResetHard(originalCommitStr); err != nil {
		fmt.Printf("Error during reset: %v\n", err)
		return 1
	}

	// Apply the changes from boil_start
	cmd := exec.Command("sh", "-c", fmt.Sprintf("git show %s | git apply --allow-empty", boilStartCommit))
	if err := cmd.Run(); err != nil {
		fmt.Printf("Error applying changes: %v\n", err)
		return 1
	}

	// Delete the boiling branch
	exec.Command("git", "branch", "-D", BoilingBranch).Run()

	fmt.Println("Successfully aborted boiling session.")
	fmt.Println("Working directory has been restored to pre-boiling state.")

	// Clean up .boil directory
	if info, err := os.Stat(".boil"); err == nil && info.IsDir() {
		fmt.Println("Removing .boil directory...")
		os.RemoveAll(".boil")
	}

	return 0
}

// FinishBoiling removes the boiling branch and folder but not the working directory state
func FinishBoiling() int {
	// Try to delete the branch
	result, _ := exec.Command("git", "branch", "-D", BoilingBranch).CombinedOutput()
	if strings.Contains(string(result), "not found") {
		fmt.Printf("Branch '%s' does not exist, nothing to delete\n", BoilingBranch)
	}

	// Clean up .boil directory
	if info, err := os.Stat(".boil"); err == nil && info.IsDir() {
		fmt.Println("Removing .boil directory...")
		os.RemoveAll(".boil")
	}

	return 0
}

// BoilCheck analyzes the current boil session and shows status/statistics
func BoilCheck() int {
	// TODO: Implement full boil check analysis
	fmt.Println("TODO: BoilCheck() not yet implemented")
	return 1
}

// DebugIterations shows detailed debug for iterations
func DebugIterations(rangeStr string) int {
	parts := strings.Split(rangeStr, "-")
	if len(parts) != 2 {
		fmt.Fprintf(os.Stderr, "Error: --debug-iterations must be in format START-END (e.g., 3-9)\n")
		return 1
	}

	start, err1 := strconv.Atoi(parts[0])
	end, err2 := strconv.Atoi(parts[1])
	if err1 != nil || err2 != nil {
		fmt.Fprintf(os.Stderr, "Error: --debug-iterations must be in format START-END (e.g., 3-9)\n")
		return 1
	}

	// TODO: Implement debug iterations
	fmt.Printf("TODO: DebugIterations(%d-%d) not yet implemented\n", start, end)
	return 1
}

// TestDetectors tests all detectors on the given error file
func TestDetectors(errorFile string) int {
	// TODO: Implement detector testing
	fmt.Printf("TODO: TestDetectors(%s) not yet implemented\n", errorFile)
	return 1
}

// IdentifyRemovable identifies functions that can be removed from the codebase
func IdentifyRemovable(files []string) int {
	// TODO: Implement or skip this feature
	fmt.Printf("TODO: IdentifyRemovable() not yet implemented\n")
	return 1
}

// AutoFixBoiler invokes an AI assistant to fix boiler for unfixable errors
func AutoFixBoiler(args []string) int {
	// TODO: Implement or skip this feature
	fmt.Println("TODO: AutoFixBoiler() not yet implemented")
	return 1
}

// DeleteAllFilesHard deletes all files in the repo before starting the boiling session
func DeleteAllFilesHard() {
	fmt.Println("=== HARD MODE: Deleting all tracked files in the repo ===")

	trackedFiles, err := GetTrackedFiles()
	if err != nil || len(trackedFiles) == 0 {
		fmt.Println("No tracked files found!")
		return
	}

	fmt.Printf("Found %d tracked files\n", len(trackedFiles))
	for _, filePath := range trackedFiles {
		if info, err := os.Stat(filePath); err == nil && !info.IsDir() {
			fmt.Printf("Deleting tracked file: %s\n", filePath)
			os.Remove(filePath)
		} else {
			fmt.Printf("Skipping non-existent file: %s\n", filePath)
		}
	}

	fmt.Println("=== All tracked files deleted ===\n")
}

// ClearRandomFileSoft picks a random file and clears its content before starting the boiling session
func ClearRandomFileSoft() {
	fmt.Println("=== SOFT MODE: Clearing content of a random tracked file ===")

	trackedFiles, err := GetTrackedFiles()
	if err != nil || len(trackedFiles) == 0 {
		fmt.Println("No tracked files found to clear!")
		return
	}

	// Pick a random file
	rand.Seed(time.Now().UnixNano())
	randomFile := trackedFiles[rand.Intn(len(trackedFiles))]
	fmt.Printf("Selected file: %s\n", randomFile)

	// Clear its content
	os.WriteFile(randomFile, []byte(""), 0644)

	fmt.Printf("=== Cleared content of %s ===\n\n", randomFile)
}

// HandleErrorFile handles pre-existing error file for analysis
func HandleErrorFile(errorFile string, ref string) int {
	data, err := os.ReadFile(errorFile)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error reading file: %v\n", err)
		return 1
	}

	errText := string(data)

	fmt.Println("[Pipeline] Attempting repair with new pipeline system...")

	gitInfo, err := GetGitFileInfo(ref)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error getting git info: %v\n", err)
		return 1
	}

	gitToplevel, _ := GetGitToplevel()
	gitState := &pipeline.GitState{
		Ref:          ref,
		DeletedFiles: gitInfo.DeletedFiles,
		GitToplevel:  gitToplevel,
		PartialFiles: gitInfo.PartialFiles,
	}

	// Assume error output is in stderr
	pipelineResult, err := pipeline.RunPipeline(errText, "", gitState, true, false)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Pipeline error: %v\n", err)
		return 1
	}

	if pipelineResult.Success {
		fmt.Printf("[Pipeline] Fixed with pipeline (modified %d file(s))\n", len(pipelineResult.FilesModified))
		return 0
	}

	fmt.Fprintln(os.Stderr, "failed to handle this type of error")
	return 1
}

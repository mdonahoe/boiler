// Main fix loop and CLI command implementations
package core

import (
	"encoding/json"
	"fmt"
	"math/rand"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
	"time"

	"github.com/mdonahoe/boiler/src/boil/ast"
	"github.com/mdonahoe/boiler/src/boil/pipeline"
)

// BoilDir is the main boil directory
const BoilDir = ".boil"

// IterationsDir is the subdirectory for iteration files (easy to delete)
const IterationsDir = ".boil/iterations"

// CleanBoilSession removes session files from .boil/ but preserves plugins/
func CleanBoilSession() {
	// Remove the iterations subdirectory
	os.RemoveAll(IterationsDir)

	// Remove boil.index if it exists
	os.Remove(filepath.Join(BoilDir, "boil.index"))
}

// Fix repeatedly runs a command, repairing files until it is fixed
func Fix(command []string, numIterations int, allowLegacy bool) (bool, error) {
	if len(command) == 0 {
		return false, fmt.Errorf("no command provided")
	}

	// Check for uncommitted additions (new files, added lines)
	// These would be lost during boiling since we restore from git history
	// Note: Deletions are allowed since deleted content exists in git history
	uncommitted, err := GetUncommittedChanges()
	if err != nil {
		return false, fmt.Errorf("failed to check for uncommitted additions: %v", err)
	}
	if len(uncommitted) > 0 {
		fmt.Fprintln(os.Stderr, "Error: Repository has uncommitted additions that would be lost by boiling:")
		for _, f := range uncommitted {
			fmt.Fprintf(os.Stderr, "  - %s\n", f)
		}
		fmt.Fprintln(os.Stderr, "\nWhile deletions are allowed since deleted content exists in git history,")
		fmt.Fprintln(os.Stderr, "new code (added files or added lines) may be deleted during boiling, losing your changes.")
		fmt.Fprintln(os.Stderr, "\nPlease commit or stash these additions before running boil.")
		return false, fmt.Errorf("uncommitted additions detected")
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
		CleanBoilSession()
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

	// Create .boil and iterations directories
	os.MkdirAll(IterationsDir, 0755)

	// Count existing iterations
	entries, _ := os.ReadDir(IterationsDir)
	n := 0
	for _, entry := range entries {
		if strings.HasPrefix(entry.Name(), "iter") && strings.HasSuffix(entry.Name(), ".pipeline.json") {
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
		errorFile := filepath.Join(IterationsDir, fmt.Sprintf("iter%d.exit%d.txt", n, code))
		if writeErr := os.WriteFile(errorFile, []byte(errOutput), 0644); writeErr != nil {
			return false, writeErr
		}

		message := ""
		exit := false

		// Build git state for pipeline (always needed for debug JSON)
		gitInfo, _ := GetGitFileInfo(ref)
		gitState := &pipeline.GitState{
			Ref:             ref,
			DeletedFiles:    gitInfo.DeletedFiles,
			GitToplevel:     gitInfo.GitToplevel,
			PartialFiles:    gitInfo.PartialFiles,
			SearchMode:      Ctx().SearchMode,
			DiscoveredFiles: Ctx().DiscoveredFiles,
		}

		// Try pipeline system
		var pipelineResult *pipeline.RepairResult
		fmt.Println("[Pipeline] Attempting repair with new pipeline system...")

		// Always run pipeline (it will return "no handlers" if none registered)
		pipelineResult, _ = pipeline.RunPipeline(stderr, stdout, gitState, true, true)

		hasChanges, _ := HasChanges()
		if pipelineResult != nil && pipelineResult.Success && hasChanges {
			message = fmt.Sprintf("fixed with pipeline (modified %d file(s))", len(pipelineResult.FilesModified))
			fmt.Printf("[Pipeline] Success: %s\n", message)
		} else {
			fmt.Println("[Pipeline] Pipeline did not produce a fix")
		}

		// Legacy handlers would go here if allowLegacy is true
		// Skipping for now since we're not implementing legacy handlers

		if message == "" {
			message = "pipeline did not produce a fix for this error"
			exit = true
		}

		// Always save debug JSON (even if pipeline didn't run or failed)
		debugJSONPath := filepath.Join(IterationsDir, fmt.Sprintf("iter%d.pipeline.json", n))
		var debugData map[string]interface{}
		if pipelineResult != nil {
			debugData = pipelineResult.ToDict()
		} else {
			// Create minimal debug data if pipeline didn't run
			debugData = map[string]interface{}{
				"success":         false,
				"error_message":   "Pipeline did not run",
				"files_modified":  []string{},
				"clues_detected":  []interface{}{},
				"plans_generated": []interface{}{},
				"plans_attempted": []interface{}{},
				"timings":         map[string]float64{},
			}
		}
		debugData["command"] = strings.Join(command, " ")
		debugData["partial_files"] = gitInfo.PartialFiles
		debugData["deleted_files"] = gitInfo.DeletedFiles
		debugData["command_time"] = tRunCommand.Seconds()

		jsonBytes, _ := json.MarshalIndent(debugData, "", "  ")
		os.WriteFile(debugJSONPath, jsonBytes, 0644)
		fmt.Printf("[Pipeline] Debug info saved to %s\n", debugJSONPath)

		hasChanges, _ = HasChanges()
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

// SearchFix runs a multi-phase search to find minimal set of lines that satisfies tests
// Phase 1: Normal fix with restore_full to discover which files are needed
// Phase 2: Trial-and-error minimization - try removing functions and keep removals that don't break tests
func SearchFix(command []string, numIterations int, allowLegacy bool) (bool, error) {
	fmt.Println("=== SEARCH MODE: Finding minimal set of lines ===")
	fmt.Println()

	// Phase 1: Discovery pass with normal restoration
	fmt.Println("=== Phase 1: Discovery (full file restoration) ===")
	success, err := Fix(command, numIterations, allowLegacy)
	if err != nil {
		return false, fmt.Errorf("phase 1 failed: %v", err)
	}
	if !success {
		return false, fmt.Errorf("phase 1 did not succeed - cannot proceed to minimization")
	}

	// Collect files that were restored during Phase 1
	discoveredFiles, err := collectRestoredFiles()
	if err != nil {
		return false, fmt.Errorf("failed to collect restored files: %v", err)
	}

	if len(discoveredFiles) == 0 {
		fmt.Println("No files were restored during Phase 1 - nothing to minimize")
		return true, nil
	}

	fmt.Printf("\nDiscovered %d file(s) during Phase 1:\n", len(discoveredFiles))
	for f := range discoveredFiles {
		fmt.Printf("  - %s\n", f)
		AddDiscoveredFile(f)
	}
	fmt.Println()

	// Phase 2: Trial-and-error minimization
	fmt.Println("=== Phase 2: Minimization (trial-and-error function removal) ===")
	removed, err := minimizeFiles(discoveredFiles, command)
	if err != nil {
		fmt.Printf("Warning: minimization encountered error: %v\n", err)
	}

	if removed > 0 {
		fmt.Printf("\n=== Search complete: Removed %d function(s) ===\n", removed)
	} else {
		fmt.Println("\n=== Search complete: No functions could be removed ===")
	}

	return true, nil
}

// minimizeFiles tries to remove functions from discovered files one by one
// Returns the number of functions successfully removed
func minimizeFiles(files map[string]bool, command []string) (int, error) {
	totalRemoved := 0

	for file := range files {
		// Only process C files for now (ast.RemoveFunctionFromFile supports C)
		if !strings.HasSuffix(file, ".c") {
			continue
		}

		removed, err := minimizeFile(file, command)
		if err != nil {
			fmt.Printf("  Warning: error minimizing %s: %v\n", file, err)
			continue
		}
		totalRemoved += removed
	}

	return totalRemoved, nil
}

// minimizeFile tries to remove functions from a single file
// Returns the number of functions successfully removed
func minimizeFile(filename string, command []string) (int, error) {
	// Get list of functions in the file
	functions, err := ast.GetFunctionNamesFromFile(filename)
	if err != nil {
		return 0, fmt.Errorf("failed to get functions: %v", err)
	}

	if len(functions) == 0 {
		return 0, nil
	}

	fmt.Printf("\nMinimizing %s (%d functions):\n", filename, len(functions))

	removed := 0
	for _, funcName := range functions {
		// Skip main function - always needed
		if funcName == "main" {
			fmt.Printf("  - %s: skipped (main)\n", funcName)
			continue
		}

		// Save original content
		original, err := os.ReadFile(filename)
		if err != nil {
			continue
		}

		// Try removing the function
		_, err = ast.RemoveFunctionFromFile(filename, funcName, true)
		if err != nil {
			fmt.Printf("  - %s: skipped (removal failed: %v)\n", funcName, err)
			continue
		}

		// Run tests
		cmd := exec.Command(command[0], command[1:]...)
		cmd.Stdout = nil
		cmd.Stderr = nil
		testErr := cmd.Run()

		if testErr == nil {
			// Tests still pass - keep the removal
			fmt.Printf("  - %s: REMOVED (tests pass without it)\n", funcName)
			removed++
		} else {
			// Tests fail - restore the function
			os.WriteFile(filename, original, 0644)
			fmt.Printf("  - %s: kept (tests need it)\n", funcName)
		}
	}

	return removed, nil
}

// collectRestoredFiles reads pipeline JSON files to find all files that were restored
func collectRestoredFiles() (map[string]bool, error) {
	files := make(map[string]bool)

	entries, err := os.ReadDir(IterationsDir)
	if err != nil {
		return files, err
	}

	for _, entry := range entries {
		if !strings.HasSuffix(entry.Name(), ".pipeline.json") {
			continue
		}

		path := filepath.Join(IterationsDir, entry.Name())
		data, err := os.ReadFile(path)
		if err != nil {
			continue
		}

		var pipelineData map[string]interface{}
		if err := json.Unmarshal(data, &pipelineData); err != nil {
			continue
		}

		// Get files_modified from the pipeline result
		if filesModified, ok := pipelineData["files_modified"].([]interface{}); ok {
			for _, f := range filesModified {
				if s, ok := f.(string); ok {
					files[s] = true
				}
			}
		}
	}

	return files, nil
}

// resetToBoilStart resets the working directory to the state right after boil_start
// This is the "broken" state before any repairs were made
func resetToBoilStart() error {
	// Find the boil_start commit on the boiling branch
	output, err := exec.Command("git", "log", "--format=%H", "--grep", "boil_start", fmt.Sprintf("HEAD..%s", BoilingBranch)).Output()
	if err != nil {
		return fmt.Errorf("could not find boil_start commit: %v", err)
	}

	commits := strings.Split(strings.TrimSpace(string(output)), "\n")
	if len(commits) == 0 || commits[0] == "" {
		return fmt.Errorf("no boil_start commit found on boiling branch")
	}

	boilStartCommit := commits[0]
	fmt.Printf("Found boil_start commit: %s\n", boilStartCommit)

	// Get the parent of boil_start (the original state)
	parentCommit, err := exec.Command("git", "rev-parse", fmt.Sprintf("%s^", boilStartCommit)).Output()
	if err != nil {
		return fmt.Errorf("could not get parent of boil_start: %v", err)
	}
	parentCommitStr := strings.TrimSpace(string(parentCommit))

	// Reset to parent (clean state)
	if err := GitResetHard(parentCommitStr); err != nil {
		return fmt.Errorf("reset to parent failed: %v", err)
	}

	// Apply the changes from boil_start (recreate the broken state)
	cmd := exec.Command("sh", "-c", fmt.Sprintf("git show %s | git apply --allow-empty", boilStartCommit))
	if err := cmd.Run(); err != nil {
		return fmt.Errorf("failed to apply boil_start changes: %v", err)
	}

	// Reset the boiling branch to point to boil_start (discard Phase 1 commits)
	if err := exec.Command("git", "branch", "-f", BoilingBranch, boilStartCommit).Run(); err != nil {
		return fmt.Errorf("failed to reset boiling branch: %v", err)
	}

	fmt.Println("Successfully reset to broken state")
	return nil
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

	// Clean up .boil session files (preserves plugins/)
	if info, err := os.Stat(".boil"); err == nil && info.IsDir() {
		fmt.Println("Cleaning up .boil session files...")
		CleanBoilSession()
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

	// Clean up .boil session files (preserves plugins/)
	if info, err := os.Stat(".boil"); err == nil && info.IsDir() {
		fmt.Println("Cleaning up .boil session files...")
		CleanBoilSession()
	}

	return 0
}

// BoilCheck analyzes the current boil session and shows status/statistics
func BoilCheck() int {
	if _, err := os.Stat(IterationsDir); os.IsNotExist(err) {
		fmt.Printf("No %s directory found. Run boil first.\n", IterationsDir)
		return 1
	}

	// Find all pipeline JSON files
	entries, err := os.ReadDir(IterationsDir)
	if err != nil {
		fmt.Printf("Error reading %s directory: %v\n", IterationsDir, err)
		return 1
	}

	var jsonFiles []string
	for _, entry := range entries {
		if strings.HasSuffix(entry.Name(), ".pipeline.json") {
			jsonFiles = append(jsonFiles, entry.Name())
		}
	}

	if len(jsonFiles) == 0 {
		fmt.Printf("No pipeline JSON files found in %s\n", IterationsDir)
		return 1
	}

	fmt.Printf("Found %d pipeline iterations\n\n", len(jsonFiles))

	// Counters
	pipelineSuccesses := 0
	pipelineFailures := 0
	errorTypesDetected := make(map[string]int)
	failureReasons := make(map[string]int)
	var allPlansAttempted []map[string]interface{}
	filesRepairedByIteration := make(map[int][]string)
	var testCommand string
	timingsByIteration := make(map[int]map[string]float64)

	// Analyze each file
	for _, jsonFile := range jsonFiles {
		path := filepath.Join(IterationsDir, jsonFile)

		data, err := os.ReadFile(path)
		if err != nil {
			fmt.Printf("Warning: Could not read %s: %v\n", jsonFile, err)
			continue
		}

		var fileData map[string]interface{}
		if err := json.Unmarshal(data, &fileData); err != nil {
			fmt.Printf("Warning: Could not parse %s: %v\n", jsonFile, err)
			continue
		}

		// Extract iteration number
		var iterNum int
		if matches := strings.Split(jsonFile, "iter"); len(matches) > 1 {
			fmt.Sscanf(matches[1], "%d", &iterNum)
		}

		// Capture test command
		if cmd, ok := fileData["command"].(string); ok && testCommand == "" {
			testCommand = cmd
		}

		// Track files repaired
		if filesModified, ok := fileData["files_modified"].([]interface{}); ok && len(filesModified) > 0 {
			var files []string
			for _, f := range filesModified {
				if s, ok := f.(string); ok {
					files = append(files, s)
				}
			}
			if len(files) > 0 {
				filesRepairedByIteration[iterNum] = files
			}
		}

		// Track timings
		if timings, ok := fileData["timings"].(map[string]interface{}); ok {
			timingMap := make(map[string]float64)
			for k, v := range timings {
				if fv, ok := v.(float64); ok {
					timingMap[k] = fv
				}
			}
			if len(timingMap) > 0 {
				timingsByIteration[iterNum] = timingMap
			}
		}

		// Count pipeline success/failure
		if success, ok := fileData["success"].(bool); ok {
			if success {
				pipelineSuccesses++
			} else {
				pipelineFailures++
				// Track failure reasons
				if errorMsg, ok := fileData["error_message"].(string); ok {
					failureReasons[errorMsg]++
				}
			}
		}

		// Count clue types detected
		if clues, ok := fileData["clues_detected"].([]interface{}); ok {
			for _, clue := range clues {
				if clueMap, ok := clue.(map[string]interface{}); ok {
					if clueType, ok := clueMap["clue_type"].(string); ok {
						errorTypesDetected[clueType]++
					}
				}
			}
		}

		// Track plans attempted
		if plans, ok := fileData["plans_attempted"].([]interface{}); ok {
			for _, plan := range plans {
				planMap := map[string]interface{}{
					"iteration": iterNum,
					"plan":      plan,
				}
				allPlansAttempted = append(allPlansAttempted, planMap)
			}
		}
	}

	// Print results
	fmt.Println(strings.Repeat("=", 80))
	fmt.Println("PIPELINE PERFORMANCE")
	fmt.Println(strings.Repeat("=", 80))
	fmt.Printf("Pipeline successes: %d\n", pipelineSuccesses)
	fmt.Printf("Pipeline failures:  %d\n", pipelineFailures)
	if pipelineSuccesses+pipelineFailures > 0 {
		successRate := float64(pipelineSuccesses) / float64(pipelineSuccesses+pipelineFailures) * 100
		fmt.Printf("Success rate:       %.1f%%\n", successRate)
	}
	fmt.Println()

	if len(failureReasons) > 0 {
		fmt.Println(strings.Repeat("=", 80))
		fmt.Println("FAILURE REASONS (Most Common)")
		fmt.Println(strings.Repeat("=", 80))
		// Sort by count (simple implementation)
		type reasonCount struct {
			reason string
			count  int
		}
		var reasons []reasonCount
		for reason, count := range failureReasons {
			reasons = append(reasons, reasonCount{reason, count})
		}
		// Sort (bubble sort for simplicity)
		for i := 0; i < len(reasons); i++ {
			for j := i + 1; j < len(reasons); j++ {
				if reasons[j].count > reasons[i].count {
					reasons[i], reasons[j] = reasons[j], reasons[i]
				}
			}
		}
		for i, rc := range reasons {
			if i >= 5 {
				break
			}
			fmt.Printf("  [%dx] %s\n", rc.count, rc.reason)
		}
		fmt.Println()
	}

	fmt.Println(strings.Repeat("=", 80))
	fmt.Println("ERROR TYPES DETECTED BY PIPELINE")
	fmt.Println(strings.Repeat("=", 80))
	if len(errorTypesDetected) > 0 {
		for errorType, count := range errorTypesDetected {
			fmt.Printf("  %-30s : %3d times\n", errorType, count)
		}
	} else {
		fmt.Println("  (none)")
	}
	fmt.Println()

	if testCommand != "" {
		fmt.Println(strings.Repeat("=", 80))
		fmt.Println("TEST COMMAND")
		fmt.Println(strings.Repeat("=", 80))
		fmt.Printf("  %s\n", testCommand)
		fmt.Println()
	}

	fmt.Println(strings.Repeat("=", 80))
	fmt.Println("FILES REPAIRED BY ITERATION")
	fmt.Println(strings.Repeat("=", 80))
	if len(filesRepairedByIteration) > 0 {
		// Sort iteration numbers
		var iterNums []int
		for iterNum := range filesRepairedByIteration {
			iterNums = append(iterNums, iterNum)
		}
		for i := 0; i < len(iterNums); i++ {
			for j := i + 1; j < len(iterNums); j++ {
				if iterNums[j] < iterNums[i] {
					iterNums[i], iterNums[j] = iterNums[j], iterNums[i]
				}
			}
		}

		allFilesRepaired := make(map[string]bool)
		for _, iterNum := range iterNums {
			files := filesRepairedByIteration[iterNum]
			for _, f := range files {
				allFilesRepaired[f] = true
			}
			fmt.Printf("  Iteration %2d: %s\n", iterNum, strings.Join(files, ", "))
		}

		fmt.Println()
		fmt.Printf("Total unique files repaired: %d\n", len(allFilesRepaired))
		var allFiles []string
		for f := range allFilesRepaired {
			allFiles = append(allFiles, f)
		}
		fmt.Printf("Files: %s\n", strings.Join(allFiles, ", "))
	} else {
		fmt.Println("  (no files were modified)")
	}
	fmt.Println()

	// If the latest iteration failed, show the error output
	if pipelineFailures > 0 && len(jsonFiles) > 0 {
		// Sort JSON files to find the latest one
		for i := 0; i < len(jsonFiles); i++ {
			for j := i + 1; j < len(jsonFiles); j++ {
				var iNum, jNum int
				fmt.Sscanf(jsonFiles[i], "iter%d", &iNum)
				fmt.Sscanf(jsonFiles[j], "iter%d", &jNum)
				if jNum > iNum {
					jsonFiles[i], jsonFiles[j] = jsonFiles[j], jsonFiles[i]
				}
			}
		}

		latestJSON := filepath.Join(IterationsDir, jsonFiles[0])
		latestData, err := os.ReadFile(latestJSON)
		if err == nil {
			var latest map[string]interface{}
			if json.Unmarshal(latestData, &latest) == nil {
				if success, ok := latest["success"].(bool); ok && !success {
					// Extract iteration number from filename
					var iterNum int
					fmt.Sscanf(jsonFiles[0], "iter%d", &iterNum)

					// Find the corresponding error output file
					var errorFile string
					for _, entry := range entries {
						name := entry.Name()
						if strings.HasPrefix(name, fmt.Sprintf("iter%d.exit", iterNum)) && strings.HasSuffix(name, ".txt") {
							errorFile = filepath.Join(IterationsDir, name)
							break
						}
					}

					if errorFile != "" {
						errOutput, err := os.ReadFile(errorFile)
						if err == nil && len(errOutput) > 0 {
							fmt.Println(strings.Repeat("=", 80))
							fmt.Println("LATEST ITERATION ERROR OUTPUT")
							fmt.Println(strings.Repeat("=", 80))
							output := string(errOutput)
							// Truncate if too long
							if len(output) > 3000 {
								output = output[:3000] + "\n... (truncated, see " + errorFile + " for full output)"
							}
							fmt.Println(output)
							fmt.Println()
						}
					}
				}
			}
		}
	}

	return 0
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
	data, err := os.ReadFile(errorFile)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error reading file: %v\n", err)
		return 1
	}

	errText := string(data)
	fmt.Println(strings.Repeat("=", 80))
	fmt.Println("TESTING ALL DETECTORS")
	fmt.Println(strings.Repeat("=", 80))

	registry := pipeline.GetDetectorRegistry()
	detectorNames := registry.ListDetectors()
	fmt.Printf("\nRegistered detectors: %d\n", len(detectorNames))
	for i, name := range detectorNames {
		fmt.Printf("  %d. %s\n", i+1, name)
	}
	fmt.Println()

	// Run detection
	clues, err := registry.DetectAll(errText, "")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Detection error: %v\n", err)
		return 1
	}

	fmt.Printf("Detected %d clue(s):\n", len(clues))
	for i, clue := range clues {
		fmt.Printf("\n--- Clue %d ---\n", i+1)
		fmt.Printf("Type: %s\n", clue.ClueType)
		fmt.Printf("Confidence: %.2f\n", clue.Confidence)
		fmt.Printf("Context: %v\n", clue.Context)
		if len(clue.SourceLine) > 100 {
			fmt.Printf("Source: %s...\n", clue.SourceLine[:100])
		} else {
			fmt.Printf("Source: %s\n", clue.SourceLine)
		}
	}

	return 0
}

// IdentifyRemovable identifies functions that can be removed from the codebase
func IdentifyRemovable(files []string) int {
	// TODO: Implement or skip this feature
	fmt.Printf("TODO: IdentifyRemovable() not yet implemented\n")
	return 1
}

// AutoFixBoiler prints a prompt for Claude to fix boiler for unfixable errors
func AutoFixBoiler(args []string) int {
	// Get repo path from args or current directory
	var repoPath string
	if len(args) > 0 {
		repoPath = args[0]
		if !filepath.IsAbs(repoPath) {
			absPath, err := filepath.Abs(repoPath)
			if err != nil {
				fmt.Fprintf(os.Stderr, "Error resolving path: %v\n", err)
				return 1
			}
			repoPath = absPath
		}
	} else {
		var err error
		repoPath, err = os.Getwd()
		if err != nil {
			fmt.Fprintf(os.Stderr, "Error getting current directory: %v\n", err)
			return 1
		}
	}

	fmt.Fprintf(os.Stderr, "Checking boiler status in: %s\n\n", repoPath)

	// Check if iterations directory exists
	iterDir := filepath.Join(repoPath, IterationsDir)
	if _, err := os.Stat(iterDir); os.IsNotExist(err) {
		fmt.Fprintf(os.Stderr, "Status: No %s directory found - boiler hasn't been run yet\n", IterationsDir)
		fmt.Fprintf(os.Stderr, "\nNothing to fix!\n")
		return 0
	}

	// Find pipeline JSON files
	entries, err := os.ReadDir(iterDir)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error reading %s directory: %v\n", IterationsDir, err)
		return 1
	}

	var pipelineFiles []string
	for _, entry := range entries {
		if strings.HasPrefix(entry.Name(), "iter") && strings.HasSuffix(entry.Name(), ".pipeline.json") {
			pipelineFiles = append(pipelineFiles, entry.Name())
		}
	}

	if len(pipelineFiles) == 0 {
		fmt.Fprintf(os.Stderr, "Status: No pipeline iteration files found\n")
		fmt.Fprintf(os.Stderr, "\nNothing to fix!\n")
		return 0
	}

	// Sort to find latest (simple string sort works for iterN format)
	for i := 0; i < len(pipelineFiles); i++ {
		for j := i + 1; j < len(pipelineFiles); j++ {
			// Extract iteration numbers for proper sorting
			var iNum, jNum int
			fmt.Sscanf(pipelineFiles[i], "iter%d", &iNum)
			fmt.Sscanf(pipelineFiles[j], "iter%d", &jNum)
			if jNum < iNum {
				pipelineFiles[i], pipelineFiles[j] = pipelineFiles[j], pipelineFiles[i]
			}
		}
	}

	latestFile := filepath.Join(iterDir, pipelineFiles[len(pipelineFiles)-1])
	data, err := os.ReadFile(latestFile)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error reading pipeline file: %v\n", err)
		return 1
	}

	var pipelineData map[string]interface{}
	if err := json.Unmarshal(data, &pipelineData); err != nil {
		fmt.Fprintf(os.Stderr, "Error parsing pipeline JSON: %v\n", err)
		return 1
	}

	// Check if boiler succeeded
	if success, ok := pipelineData["success"].(bool); ok && success {
		fmt.Fprintf(os.Stderr, "Status: Boiler succeeded - no fix needed\n")
		fmt.Fprintf(os.Stderr, "\nNothing to fix!\n")
		return 0
	}

	fmt.Fprintf(os.Stderr, "Status: Boiler FAILED - automatic fix needed\n\n")

	// Get error summary by running boil --check
	errorSummary := getErrorSummary(repoPath)

	// Create and print prompt
	prompt := createClaudePrompt(repoPath, errorSummary)
	fmt.Println(prompt)

	return 0
}

// getErrorSummary runs boil --check and captures output
func getErrorSummary(repoPath string) string {
	// Find the boil binary (use the one in PATH or build directory)
	boilBinary := "boil"

	cmd := exec.Command(boilBinary, "--check")
	cmd.Dir = repoPath
	output, _ := cmd.CombinedOutput()
	return string(output)
}

// createClaudePrompt creates the prompt to send to Claude
func createClaudePrompt(repoPath string, errorSummary string) string {
	return fmt.Sprintf(`I need your help creating boiler plugins to handle errors in this repository.

WORKING DIRECTORY:
%s

CURRENT SITUATION:
Boiler has failed to fix errors in this repository.

Status from 'boil --check':
%s

YOUR TASK:
Create plugins in %s/.boil/plugins/ to handle this error pattern.

1. Analyze the debugging information in %s/.boil/iterations/
   - Read the iter*.pipeline.json files to see what clues were detected
   - Read the iter*.exit*.txt files to see the actual error output
   - Identify what error pattern boiler couldn't handle

2. Create a detector plugin (if the error isn't being detected):
   - Create %s/.boil/plugins/detectors/<name>.json
   - Use regex patterns with named groups to extract context
   - Example format:
     {
       "name": "MyDetector",
       "patterns": {
         "my_error_type": "error: (?P<message>.+) in (?P<file>.+)"
       },
       "examples": [
         {"input": "error: failed in foo.txt", "clue_type": "my_error_type", "context": {"message": "failed", "file": "foo.txt"}}
       ]
     }

3. Create a planner plugin (if the error is detected but not fixed):
   - Create %s/.boil/plugins/planners/<name>.star
   - Starlark planners can use: git_show(), git_grep(), file_exists(), read_file(), regex_match()
   - Must define: name(), can_handle(clue_type), plan(clues, git_state)
   - Return plans with: plan_type, action, target_file, params, reason

4. Test by running: boil --abort && boil make test
   - Use BOIL_VERBOSE=1 to see plugin loading and plan generation

See ~/boiler/AGENTS.md "Plugin System" section for detailed documentation.
`, repoPath, errorSummary, repoPath, repoPath, repoPath, repoPath)
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
	deleted := 0
	for _, filePath := range trackedFiles {
		// Skip .boil/ directory - it contains plugins and session data
		if strings.HasPrefix(filePath, ".boil/") || strings.HasPrefix(filePath, ".boil\\") {
			fmt.Printf("Preserving .boil file: %s\n", filePath)
			continue
		}
		if info, err := os.Stat(filePath); err == nil && !info.IsDir() {
			fmt.Printf("Deleting tracked file: %s\n", filePath)
			os.Remove(filePath)
			deleted++
		} else {
			fmt.Printf("Skipping non-existent file: %s\n", filePath)
		}
	}

	fmt.Printf("=== Deleted %d tracked files (.boil/ preserved) ===\n", deleted)
}

// ClearRandomFileSoft picks a random file and clears its content before starting the boiling session
func ClearRandomFileSoft() {
	fmt.Println("=== SOFT MODE: Clearing content of a random tracked file ===")

	trackedFiles, err := GetTrackedFiles()
	if err != nil || len(trackedFiles) == 0 {
		fmt.Println("No tracked files found to clear!")
		return
	}

	// Filter out files with 'test' in the name (case-insensitive)
	// Test files are important for boiler to function and should not be cleared
	var eligibleFiles []string
	for _, f := range trackedFiles {
		lowerPath := strings.ToLower(f)
		if !strings.Contains(lowerPath, "test") {
			eligibleFiles = append(eligibleFiles, f)
		}
	}

	if len(eligibleFiles) == 0 {
		fmt.Println("No eligible files found to clear (all files contain 'test' in name)!")
		return
	}

	fmt.Printf("Found %d eligible files (excluded %d test files)\n", len(eligibleFiles), len(trackedFiles)-len(eligibleFiles))

	// Pick a random file
	rand.Seed(time.Now().UnixNano())
	randomFile := eligibleFiles[rand.Intn(len(eligibleFiles))]
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

	fmt.Fprintln(os.Stderr, "womp womp")
	return 1
}

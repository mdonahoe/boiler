// Helper functions for running commands
package core

import (
	"bytes"
	"fmt"
	"os"
	"os/exec"
	"strings"
)

// RunCommand runs a shell command and returns its stdout, stderr, and exit code.
//
// Returns standard Unix exit codes:
// - 126: Permission denied
// - 127: Command not found
func RunCommand(command []string) (string, string, int) {
	if len(command) == 0 {
		return "", "Error: empty command", 1
	}

	fmt.Printf("Running: %s\n", strings.Join(command, " "))

	cmd := exec.Command(command[0], command[1:]...)
	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr

	err := cmd.Run()

	stdoutStr := stdout.String()
	stderrStr := stderr.String()

	if err != nil {
		// Check for specific error types
		if _, ok := err.(*exec.ExitError); ok {
			// Command ran but returned non-zero exit code
			return stdoutStr, stderrStr, cmd.ProcessState.ExitCode()
		}

		// Check for file not found error
		if err == exec.ErrNotFound || strings.Contains(err.Error(), "executable file not found") {
			return "", fmt.Sprintf("FileNotFoundError: %v", err), 127
		}

		// Check for permission denied error
		if os.IsPermission(err) {
			return "", fmt.Sprintf("PermissionError: %v", err), 126
		}

		// Other errors
		return stdoutStr, stderrStr, 1
	}

	return stdoutStr, stderrStr, 0
}

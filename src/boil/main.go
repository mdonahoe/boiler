// Main entry point for the boil command
package main

import (
	"flag"
	"fmt"
	"os"
	"strings"

	"github.com/mdonahoe/boiler/src/boil/core"
)

func main() {
	// Define flags
	n := flag.Int("n", 0, "number of iterations")
	maxIterations := n // Alias for clarity
	ref := flag.String("ref", "HEAD", "a working commit")
	abort := flag.Bool("abort", false, "abort current boiling session and restore working directory")
	finish := flag.Bool("finish", false, "remove the boiling branch and folder but not the working directory state")
	handleError := flag.String("handle-error", "", "path to pre-existing command output for error analysis")
	check := flag.Bool("check", false, "analyze the current boil session and show status/statistics")
	legacy := flag.Bool("legacy", false, "fallback to legacy handlers if needed")
	debugIterations := flag.String("debug-iterations", "", "debug specific iterations when using --check (e.g., 3-9)")
	testDetectors := flag.String("test-detectors", "", "test all detectors on the given error file and show verbose output")
	identifyRemovable := flag.String("identify-removable", "", "identify functions that can be removed from the codebase (comma-separated files)")
	fix := flag.String("fix", "", "invoke an AI assistant to fix boiler for unfixable errors (choices: claude)")
	hard := flag.Bool("hard", false, "delete all files in the repo before starting the boiling session")
	soft := flag.Bool("soft", false, "pick a random file and clear its content before starting the boiling session")

	// Parse flags
	flag.Parse()

	// Handle special commands
	if *abort {
		os.Exit(core.AbortBoiling())
	}

	if *finish {
		os.Exit(core.FinishBoiling())
	}

	if *check {
		if *debugIterations != "" {
			os.Exit(core.DebugIterations(*debugIterations))
		}
		os.Exit(core.BoilCheck())
	}

	if *testDetectors != "" {
		os.Exit(core.TestDetectors(*testDetectors))
	}

	if *identifyRemovable != "" {
		files := strings.Split(*identifyRemovable, ",")
		os.Exit(core.IdentifyRemovable(files))
	}

	if *fix != "" {
		if *fix != "claude" {
			fmt.Fprintf(os.Stderr, "Error: Unknown fix method '%s'\n", *fix)
			os.Exit(1)
		}
		os.Exit(core.AutoFixBoiler(flag.Args()))
	}

	// Remaining args are the command
	command := flag.Args()

	// Validate hard/soft modes
	if *hard && *soft {
		fmt.Fprintln(os.Stderr, "Error: Cannot use both --hard and --soft at the same time")
		os.Exit(1)
	}

	if (*hard || *soft) && len(command) == 0 {
		fmt.Fprintln(os.Stderr, "Error: --hard and --soft require a test command (e.g., 'boil --soft make test')")
		os.Exit(1)
	}

	if *hard {
		core.DeleteAllFilesHard()
	}

	if *soft {
		core.ClearRandomFileSoft()
	}

	// Set the global session
	core.NewSession("foo", *ref, 0, command)

	// Register pipeline handlers
	fmt.Println("[Pipeline] Registering pipeline handlers...")
	// TODO: Call handlers.RegisterAllHandlers() when implemented

	// Handle error mode
	if *handleError != "" {
		os.Exit(core.HandleErrorFile(*handleError, *ref))
	}

	// Main fix loop
	success, err := core.Fix(command, *maxIterations, *legacy)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error: %v\n", err)
		os.Exit(1)
	}

	if !success {
		fmt.Printf("failed to fix: %s\n", strings.Join(command, " "))
		os.Exit(1)
	}

	fmt.Println("success")
	os.Exit(0)
}

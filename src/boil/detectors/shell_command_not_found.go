// Detector for shell command not found errors.
package detectors

// ShellCommandNotFoundDetector detects shell command not found errors
type ShellCommandNotFoundDetector struct {
	*BaseDetector
}

func NewShellCommandNotFoundDetector() (*ShellCommandNotFoundDetector, error) {
	base, err := NewBaseDetector(
		"ShellCommandNotFoundDetector",
		100,
		map[string]string{
			"missing_file":           `:\s*line\s+\d+:\s*\.?/?(?P<file_path>[^\s:]+):\s*No such file or directory`,
			"missing_file_not_found": `:\s*\d+:\s*\.?/?(?P<file_path>[^\s:]+):\s*not found`,
		},
		[]DetectorExample{
			{
				Name:     "shell_no_such_file",
				Input:    "bash: line 5: ./run.sh: No such file or directory",
				ClueType: "missing_file",
				Context:  map[string]string{"file_path": "run.sh"},
			},
			{
				Name:     "shell_not_found",
				Input:    "sh: 1: ./script: not found",
				ClueType: "missing_file_not_found",
				Context:  map[string]string{"file_path": "script"},
			},
		},
	)
	if err != nil {
		return nil, err
	}
	return &ShellCommandNotFoundDetector{base}, nil
}

// Detector for shell "cannot open" errors.
package detectors

// ShellCannotOpenDetector detects shell "cannot open" errors
type ShellCannotOpenDetector struct {
	*BaseDetector
}

func NewShellCannotOpenDetector() (*ShellCannotOpenDetector, error) {
	base, err := NewBaseDetector(
		"ShellCannotOpenDetector",
		100,
		map[string]string{
			"missing_file": `sh:\s*\d+:\s*cannot open\s+(?P<file_path>[^\s:]+):\s*No such file`,
		},
		[]DetectorExample{
			{
				Name:     "shell_cannot_open",
				Input:    "sh: 1: cannot open config.sh: No such file",
				ClueType: "missing_file",
				Context:  map[string]string{"file_path": "config.sh"},
			},
		},
	)
	if err != nil {
		return nil, err
	}
	return &ShellCannotOpenDetector{base}, nil
}

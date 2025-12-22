// Detector for Python FileNotFoundError.
package detectors

// FileNotFoundDetector detects Python FileNotFoundError
type FileNotFoundDetector struct {
	*BaseDetector
}

func NewFileNotFoundDetector() (*FileNotFoundDetector, error) {
	base, err := NewBaseDetector(
		"FileNotFoundDetector",
		100,
		map[string]string{
			"missing_file":        `FileNotFoundError:.*?No such file or directory:\s*['"](?P<file_path>[^'"]+)['"]`,
			"missing_file_simple": `FileNotFoundError:\s*(?P<file_path>[^\s:]+)`,
		},
		[]DetectorExample{
			{
				Name:     "python_file_not_found",
				Input:    "FileNotFoundError: [Errno 2] No such file or directory: './test.sh'",
				ClueType: "missing_file",
				Context:  map[string]string{"file_path": "./test.sh"},
			},
			{
				Name:     "python_file_not_found_simple",
				Input:    "FileNotFoundError: ./configure",
				ClueType: "missing_file_simple",
				Context:  map[string]string{"file_path": "./configure"},
			},
		},
	)
	if err != nil {
		return nil, err
	}
	return &FileNotFoundDetector{base}, nil
}

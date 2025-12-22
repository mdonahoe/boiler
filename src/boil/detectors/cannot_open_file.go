// Detector for "Cannot open file" errors.
package detectors

// CannotOpenFileDetector detects "Cannot open file" errors
type CannotOpenFileDetector struct {
	*BaseDetector
}

func NewCannotOpenFileDetector() (*CannotOpenFileDetector, error) {
	base, err := NewBaseDetector(
		"CannotOpenFileDetector",
		100,
		map[string]string{
			"missing_file": `[Ee]rror:?\s+Cannot open file\s+['"](?P<file_path>[^'"]+)['"]`,
		},
		[]DetectorExample{
			{
				Name:     "cannot_open_single_quotes",
				Input:    "Error: Cannot open file 'config.json'",
				ClueType: "missing_file",
				Context:  map[string]string{"file_path": "config.json"},
			},
			{
				Name:     "cannot_open_double_quotes",
				Input:    `error Cannot open file "main.py"`,
				ClueType: "missing_file",
				Context:  map[string]string{"file_path": "main.py"},
			},
		},
	)
	if err != nil {
		return nil, err
	}
	return &CannotOpenFileDetector{base}, nil
}

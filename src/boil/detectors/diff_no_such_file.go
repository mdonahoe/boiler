// Detector for diff command "No such file" errors.
package detectors

// DiffNoSuchFileDetector detects diff command "No such file" errors
type DiffNoSuchFileDetector struct {
	*BaseDetector
}

func NewDiffNoSuchFileDetector() (*DiffNoSuchFileDetector, error) {
	base, err := NewBaseDetector(
		"DiffNoSuchFileDetector",
		100,
		map[string]string{
			"missing_file": `diff:\s*(?P<file_path>[^\s:]+):\s*No such file or directory`,
		},
		[]DetectorExample{
			{
				Name:     "diff_missing_file",
				Input:    "diff: expected.txt: No such file or directory",
				ClueType: "missing_file",
				Context:  map[string]string{"file_path": "expected.txt"},
			},
		},
	)
	if err != nil {
		return nil, err
	}
	return &DiffNoSuchFileDetector{base}, nil
}

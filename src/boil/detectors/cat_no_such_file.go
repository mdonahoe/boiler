// Detector for cat errors when a file is missing.
package detectors

// CatNoSuchFileDetector detects cat command "No such file" errors
type CatNoSuchFileDetector struct {
	*BaseDetector
}

func NewCatNoSuchFileDetector() (*CatNoSuchFileDetector, error) {
	base, err := NewBaseDetector(
		"CatNoSuchFileDetector",
		100,
		map[string]string{
			"missing_file": `cat:\s*(?P<file_path>[^\s:]+):\s*No such file or directory`,
		},
		[]DetectorExample{
			{
				Name:     "cat_missing_makefile",
				Input:    "cat: Makefile.in: No such file or directory",
				ClueType: "missing_file",
				Context:  map[string]string{"file_path": "Makefile.in"},
			},
			{
				Name:     "cat_missing_config",
				Input:    "cat: config.txt: No such file or directory",
				ClueType: "missing_file",
				Context:  map[string]string{"file_path": "config.txt"},
			},
		},
	)
	if err != nil {
		return nil, err
	}
	return &CatNoSuchFileDetector{base}, nil
}

// Detector for make glob pattern errors.
package detectors

// MakeGlobPatternErrorDetector detects make glob pattern errors
type MakeGlobPatternErrorDetector struct {
	*BaseDetector
}

func NewMakeGlobPatternErrorDetector() (*MakeGlobPatternErrorDetector, error) {
	base, err := NewBaseDetector(
		"MakeGlobPatternErrorDetector",
		100,
		map[string]string{
			"missing_file": `make(?:\[\d+\])?: \*\*\* (?P<file_path>[^:]+):\s+No such file or directory\.\s+Stop\.`,
		},
		[]DetectorExample{
			{
				Name:     "make_glob_missing",
				Input:    "make: *** Makefile.inc: No such file or directory.  Stop.",
				ClueType: "missing_file",
				Context:  map[string]string{"file_path": "Makefile.inc"},
			},
		},
	)
	if err != nil {
		return nil, err
	}
	return &MakeGlobPatternErrorDetector{base}, nil
}

// Detector for make missing target errors.
package detectors

// MakeMissingTargetDetector detects make missing target errors
type MakeMissingTargetDetector struct {
	*BaseDetector
}

func NewMakeMissingTargetDetector() (*MakeMissingTargetDetector, error) {
	base, err := NewBaseDetector(
		"MakeMissingTargetDetector",
		100,
		map[string]string{
			"make_missing_target": `No rule to make target '(?P<target>[^']+)', needed by '(?P<needed_by>[^']+)'`,
		},
		[]DetectorExample{
			{
				Name:     "make_missing_target",
				Input:    "No rule to make target 'utils.o', needed by 'main'",
				ClueType: "make_missing_target",
				Context: map[string]string{
					"target":    "utils.o",
					"needed_by": "main",
				},
			},
		},
	)
	if err != nil {
		return nil, err
	}
	return &MakeMissingTargetDetector{base}, nil
}

// Detector for make "No rule to make target" errors.
package detectors

// MakeNoRuleDetector detects make "No rule to make target" errors
type MakeNoRuleDetector struct {
	*BaseDetector
}

func NewMakeNoRuleDetector() (*MakeNoRuleDetector, error) {
	base, err := NewBaseDetector(
		"MakeNoRuleDetector",
		100,
		map[string]string{
			"make_no_rule": `make(?:\[\d+\])?: \*\*\* No rule to make target '(?P<target>[^']+)'\.\s+Stop\.`,
		},
		[]DetectorExample{
			{
				Name:     "make_no_rule",
				Input:    "make: *** No rule to make target 'test'.  Stop.",
				ClueType: "make_no_rule",
				Context:  map[string]string{"target": "test"},
			},
			{
				Name:     "make_no_rule_with_level",
				Input:    "make[2]: *** No rule to make target 'build'.  Stop.",
				ClueType: "make_no_rule",
				Context:  map[string]string{"target": "build"},
			},
		},
	)
	if err != nil {
		return nil, err
	}
	return &MakeNoRuleDetector{base}, nil
}

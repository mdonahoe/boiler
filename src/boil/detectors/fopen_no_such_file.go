// Detector for fopen "No such file" errors.
package detectors

// FopenNoSuchFileDetector detects fopen "No such file" errors
type FopenNoSuchFileDetector struct {
	*BaseDetector
}

func NewFopenNoSuchFileDetector() (*FopenNoSuchFileDetector, error) {
	base, err := NewBaseDetector(
		"FopenNoSuchFileDetector",
		100,
		map[string]string{
			"missing_file":           `fopen:\s+(?P<file_path>[^\s:]+?):\s*No such file or directory`,
			"missing_file_assertion": `AssertionError:\s*['"](?P<file_path>[^'"]+\.(?:py|txt|md|c|h|cpp|hpp|json|yaml|yml|sh|rs|go|java|js|ts|html|css|xml|sql))['"].*fopen:\s*No such file or directory`,
		},
		[]DetectorExample{
			{
				Name:     "fopen_missing_file",
				Input:    "fopen: config.txt: No such file or directory",
				ClueType: "missing_file",
				Context:  map[string]string{"file_path": "config.txt"},
			},
			{
				Name:     "fopen_assertion",
				Input:    `AssertionError: "test.py" something something fopen: No such file or directory`,
				ClueType: "missing_file_assertion",
				Context:  map[string]string{"file_path": "test.py"},
			},
		},
	)
	if err != nil {
		return nil, err
	}
	return &FopenNoSuchFileDetector{base}, nil
}

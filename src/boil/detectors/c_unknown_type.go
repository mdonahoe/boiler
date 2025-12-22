// Detector for C unknown type name errors.
package detectors

// CUnknownTypeDetector detects C unknown type name errors
type CUnknownTypeDetector struct {
	*BaseDetector
}

func NewCUnknownTypeDetector() (*CUnknownTypeDetector, error) {
	base, err := NewBaseDetector(
		"CUnknownTypeDetector",
		100,
		map[string]string{
			"unknown_type_name": `(?P<file_path>[a-zA-Z0-9_./\-]+\.c):(?P<line_number>\d+):\d+:\s+error:\s+unknown type name\s+[''](?P<type_name>[^'']+)['']`,
		},
		[]DetectorExample{
			{
				Name:     "unknown_type_size_t",
				Input:    "utils.c:8:1: error: unknown type name 'size_t'",
				ClueType: "unknown_type_name",
				Context: map[string]string{
					"file_path":   "utils.c",
					"line_number": "8",
					"type_name":   "size_t",
				},
			},
		},
	)
	if err != nil {
		return nil, err
	}
	return &CUnknownTypeDetector{base}, nil
}

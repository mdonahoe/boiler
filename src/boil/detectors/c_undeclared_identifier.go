// Detector for C undeclared identifier errors.
package detectors

// CUndeclaredIdentifierDetector detects C undeclared identifier errors
type CUndeclaredIdentifierDetector struct {
	*BaseDetector
}

func NewCUndeclaredIdentifierDetector() (*CUndeclaredIdentifierDetector, error) {
	base, err := NewBaseDetector(
		"CUndeclaredIdentifierDetector",
		100,
		map[string]string{
			"missing_c_include":  `(?P<file_path>[a-zA-Z0-9_./\-]+\.c):\d+:\d+:[^\n]*undeclared.*note:.*is defined in header\s+['']<(?P<suggested_include>[^>]+)>['']`,
			"missing_c_function": `(?P<file_path>[a-zA-Z0-9_./\-]+\.c):(?P<line_number>\d+):\d+:\s+error:\s+[''](?P<identifier>[^'']+)['']\s+undeclared\s+\(first use`,
		},
		[]DetectorExample{
			{
				Name:     "undeclared_with_header_note",
				Input:    "main.c:5:12: 'NULL' undeclared here (not in a function); note: 'NULL' is defined in header '<stddef.h>'",
				ClueType: "missing_c_include",
				Context: map[string]string{
					"file_path":         "main.c",
					"suggested_include": "stddef.h",
				},
			},
			{
				Name:     "undeclared_first_use",
				Input:    "test.c:20:10: error: 'my_var' undeclared (first use",
				ClueType: "missing_c_function",
				Context: map[string]string{
					"file_path":   "test.c",
					"line_number": "20",
					"identifier":  "my_var",
				},
			},
		},
	)
	if err != nil {
		return nil, err
	}
	return &CUndeclaredIdentifierDetector{base}, nil
}

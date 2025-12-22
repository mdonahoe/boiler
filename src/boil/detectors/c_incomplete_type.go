// Detector for C incomplete type errors.
package detectors

// CIncompleteTypeDetector detects C incomplete type errors
type CIncompleteTypeDetector struct {
	*BaseDetector
}

func NewCIncompleteTypeDetector() (*CIncompleteTypeDetector, error) {
	base, err := NewBaseDetector(
		"CIncompleteTypeDetector",
		100,
		map[string]string{
			"missing_c_include": `(?P<file_path>[a-zA-Z0-9_./\-]+\.c):\d+:\d+:[^\n]*error:[^\n]*(?:has incomplete type|storage size).*struct\s+(?P<struct_name>termios|winsize|stat|tm|sigaction|dirent)`,
		},
		[]DetectorExample{
			{
				Name:     "incomplete_type_termios",
				Input:    "term.c:15:3: error: variable has incomplete type 'struct termios'",
				ClueType: "missing_c_include",
				Context: map[string]string{
					"file_path":   "term.c",
					"struct_name": "termios",
				},
			},
			{
				Name:     "storage_size_winsize",
				Input:    "window.c:8:12: error: storage size of 'ws' isn't known struct winsize",
				ClueType: "missing_c_include",
				Context: map[string]string{
					"file_path":   "window.c",
					"struct_name": "winsize",
				},
			},
		},
	)
	if err != nil {
		return nil, err
	}
	return &CIncompleteTypeDetector{base}, nil
}

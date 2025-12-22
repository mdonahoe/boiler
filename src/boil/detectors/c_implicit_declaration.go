// Detector for C implicit function declaration errors.
package detectors

// CImplicitDeclarationDetector detects C implicit function declaration errors
type CImplicitDeclarationDetector struct {
	*BaseDetector
}

func NewCImplicitDeclarationDetector() (*CImplicitDeclarationDetector, error) {
	base, err := NewBaseDetector(
		"CImplicitDeclarationDetector",
		100,
		map[string]string{
			"missing_c_include":  `(?P<file_path>[a-zA-Z0-9_./\-]+\.c):\d+:\d+:\s+(?:error|warning):\s+implicit declaration of function\s+[''](?P<function_name>[^'']+)[''].*?note:\s+include\s+['']<(?P<suggested_include>[^>]+)>['']`,
			"missing_c_function": `(?P<file_path>[a-zA-Z0-9_./\-]+\.c):(?P<line_number>\d+):\d+:\s+(?:error|warning):\s+implicit declaration of function\s+[''](?P<function_name>[^'']+)['']`,
		},
		[]DetectorExample{
			{
				Name:     "implicit_declaration_with_note",
				Input:    "main.c:10:5: warning: implicit declaration of function 'printf' [-Wimplicit-function-declaration] note: include '<stdio.h>'",
				ClueType: "missing_c_include",
				Context: map[string]string{
					"file_path":         "main.c",
					"function_name":     "printf",
					"suggested_include": "stdio.h",
				},
			},
			{
				Name:     "implicit_declaration_simple",
				Input:    "test.c:42:8: error: implicit declaration of function 'custom_func'",
				ClueType: "missing_c_function",
				Context: map[string]string{
					"file_path":     "test.c",
					"line_number":   "42",
					"function_name": "custom_func",
				},
			},
		},
	)
	if err != nil {
		return nil, err
	}
	return &CImplicitDeclarationDetector{base}, nil
}

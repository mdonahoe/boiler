// Detector for C/C++ compilation errors for missing files.
package detectors

// CCompilationErrorDetector detects C/C++ compilation errors for missing files
type CCompilationErrorDetector struct {
	*BaseDetector
}

func NewCCompilationErrorDetector() (*CCompilationErrorDetector, error) {
	base, err := NewBaseDetector(
		"CCompilationErrorDetector",
		100,
		map[string]string{
			"missing_file": `fatal error:\s+\.?/?(?P<file_path>[^\s:]+):\s+No such file or directory`,
		},
		[]DetectorExample{
			{
				Name:     "fatal_error_header",
				Input:    "/tmp/ex_bar.c:82:10: fatal error: ex.h: No such file or directory",
				ClueType: "missing_file",
				Context:  map[string]string{"file_path": "ex.h"},
			},
			{
				Name:     "fatal_error_relative_path",
				Input:    "lib/src/node.c:2:10: fatal error: ./point.h: No such file or directory",
				ClueType: "missing_file",
				Context:  map[string]string{"file_path": "point.h"},
			},
		},
	)
	if err != nil {
		return nil, err
	}
	return &CCompilationErrorDetector{base}, nil
}

// Detector for C/C++ syntax errors.
package detectors

// CSyntaxErrorDetector detects C/C++ syntax errors
type CSyntaxErrorDetector struct {
	*BaseDetector
}

func NewCSyntaxErrorDetector() (*CSyntaxErrorDetector, error) {
	base, err := NewBaseDetector(
		"CSyntaxErrorDetector",
		100,
		map[string]string{
			"c_syntax_error_in_header": `(?P<file_path>[^\s:]+\.h):(?P<line_number>\d+):\d+:\s+error:\s+expected\s+.+?\s+before\s+[''](?P<unexpected_token>[^'']+)['']`,
			"c_syntax_error_in_source": `(?P<file_path>[^\s:]+\.c):(?P<line_number>\d+):\d+:\s+error:\s+expected\s+.+?\s+before\s+[''](?P<unexpected_token>[^'']+)['']`,
		},
		[]DetectorExample{
			{
				Name:     "syntax_error_header",
				Input:    "include/api.h:15:1: error: expected ';' before 'typedef'",
				ClueType: "c_syntax_error_in_header",
				Context: map[string]string{
					"file_path":        "include/api.h",
					"line_number":      "15",
					"unexpected_token": "typedef",
				},
			},
			{
				Name:     "syntax_error_source",
				Input:    "main.c:42:5: error: expected declaration before 'return'",
				ClueType: "c_syntax_error_in_source",
				Context: map[string]string{
					"file_path":        "main.c",
					"line_number":      "42",
					"unexpected_token": "return",
				},
			},
		},
	)
	if err != nil {
		return nil, err
	}
	return &CSyntaxErrorDetector{base}, nil
}

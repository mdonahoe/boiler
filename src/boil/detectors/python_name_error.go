// Detector for Python NameError exceptions.
package detectors

// PythonNameErrorDetector detects Python NameError exceptions
type PythonNameErrorDetector struct {
	*BaseDetector
}

func NewPythonNameErrorDetector() (*PythonNameErrorDetector, error) {
	base, err := NewBaseDetector(
		"PythonNameErrorDetector",
		100,
		map[string]string{
			"python_name_error": `File "(?P<file_path>[^"]+\.py)", line (?P<line_number>\d+),.*?NameError: (?:global )?name '(?P<undefined_name>\w+)' is not defined`,
		},
		[]DetectorExample{
			{
				Name:     "python_name_error",
				Input:    `File "test.py", line 10, in main NameError: name 'undefined_var' is not defined`,
				ClueType: "python_name_error",
				Context: map[string]string{
					"file_path":      "test.py",
					"line_number":    "10",
					"undefined_name": "undefined_var",
				},
			},
		},
	)
	if err != nil {
		return nil, err
	}
	return &PythonNameErrorDetector{base}, nil
}

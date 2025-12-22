// Detector for test failure patterns.
package detectors

// TestFailureDetector detects test failure patterns
type TestFailureDetector struct {
	*BaseDetector
}

func NewTestFailureDetector() (*TestFailureDetector, error) {
	base, err := NewBaseDetector(
		"TestFailureDetector",
		100,
		map[string]string{
			"test_failure":                 `File\s+['"](?P<test_file>[^'"]+\.py)['"]\s*,\s+line\s+(?P<line_number>\d+),\s+in\s+(?P<test_name>\w+)`,
			"test_assertion_with_filename": `AssertionError:\s*['"](?P<suspected_file>[^'"]+\.(?:py|txt|md|c|h|cpp|hpp|json|yaml|yml|sh))['"].*not found`,
			"c_test_failure":               "(?P<test_file>[^\\s:]+\\.c):(?P<line_number>\\d+):\\s*(?P<test_name>\\w+):\\s*Assertion\\s*[`'](?P<assertion>[^'`]+)[`']\\s*failed",
			// (?s) enables single-line mode where . matches newlines (equivalent to Python's re.DOTALL)
			"test_docstring_with_missing_file": `(?s)Test that[^\n]*(?:can open|open)\s+(?P<suspected_file>(?:README\.md|[a-zA-Z0-9_-]+\.(?:c|h|cpp|hpp|py|txt|md|json|yaml|yml|sh|rs|go|java|js|ts))).*?fopen:\s*No such file or directory`,
		},
		[]DetectorExample{
			{
				Name:     "python_test_failure",
				Input:    `File "/path/to/test_dim.py", line 235, in test_open_readme`,
				ClueType: "test_failure",
				Context: map[string]string{
					"test_file":   "/path/to/test_dim.py",
					"line_number": "235",
					"test_name":   "test_open_readme",
				},
			},
			{
				Name:     "assertion_with_filename",
				Input:    "AssertionError: 'hello_world.txt' not found",
				ClueType: "test_assertion_with_filename",
				Context:  map[string]string{"suspected_file": "hello_world.txt"},
			},
			{
				Name:     "c_test_failure",
				Input:    "test_runner.c:42: test_addition: Assertion `result == 5` failed",
				ClueType: "c_test_failure",
				Context: map[string]string{
					"test_file":   "test_runner.c",
					"line_number": "42",
					"test_name":   "test_addition",
					"assertion":   "result == 5",
				},
			},
			{
				// Multiline test - (?s) flag enables . to match newlines
				Name: "test_docstring_with_missing_file",
				Input: `Test that dim can open README.md and display its first line.
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/tmp/test_dim.py", line 235, in test_open_readme
    self.assertIn("dim", result.output)
AssertionError: 'dim' not found in 'fopen: No such file or directory'`,
				ClueType: "test_docstring_with_missing_file",
				Context:  map[string]string{"suspected_file": "README.md"},
			},
		},
	)
	if err != nil {
		return nil, err
	}
	return &TestFailureDetector{base}, nil
}

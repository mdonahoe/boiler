// Unit tests for detector implementations.
//
// Each test case verifies that a detector's regex patterns correctly match
// example error messages and extract the expected context values.
package detectors

import (
	"testing"

	"github.com/mdonahoe/boiler/src/boil/pipeline"
)

// DetectorExample represents a test case for a detector
type DetectorExample struct {
	Name        string            // Human-readable name for the test case
	Input       string            // Error text to match against
	ClueType    string            // Expected clue type
	Context     map[string]string // Expected context values
}

// verifyClues is a helper that checks if clues match expectations
func verifyClues(t *testing.T, clues []*pipeline.ErrorClue, ex DetectorExample) {
	t.Helper()

	if len(clues) == 0 {
		t.Fatalf("Expected at least 1 clue, got 0\nInput: %s", ex.Input)
	}

	// Find a clue with matching ClueType
	var clue *pipeline.ErrorClue
	for _, c := range clues {
		if c.ClueType == ex.ClueType {
			clue = c
			break
		}
	}

	if clue == nil {
		clueTypes := make([]string, len(clues))
		for i, c := range clues {
			clueTypes[i] = c.ClueType
		}
		t.Fatalf("Expected clue type %q not found, got: %v", ex.ClueType, clueTypes)
	}

	for key, expectedValue := range ex.Context {
		actualValue, ok := clue.Context[key]
		if !ok {
			t.Errorf("Context missing key %q\nExpected: %v\nGot: %v", key, ex.Context, clue.Context)
			continue
		}
		if actualValue != expectedValue {
			t.Errorf("Context[%q] mismatch: expected %q, got %q", key, expectedValue, actualValue)
		}
	}
}

// TestCannotOpenFileDetector tests the CannotOpenFileDetector
func TestCannotOpenFileDetector(t *testing.T) {
	detector, err := NewCannotOpenFileDetector()
	if err != nil {
		t.Fatalf("Failed to create detector: %v", err)
	}

	examples := []DetectorExample{
		{
			Name:     "cannot_open_single_quotes",
			Input:    "Error: Cannot open file 'config.json'",
			ClueType: "missing_file",
			Context:  map[string]string{"file_path": "config.json"},
		},
		{
			Name:     "cannot_open_double_quotes",
			Input:    `error Cannot open file "main.py"`,
			ClueType: "missing_file",
			Context:  map[string]string{"file_path": "main.py"},
		},
	}

	for _, ex := range examples {
		t.Run(ex.Name, func(t *testing.T) {
			clues, err := detector.Detect(ex.Input, "")
			if err != nil {
				t.Fatalf("Detect() returned error: %v", err)
			}
			verifyClues(t, clues, ex)
		})
	}
}

// TestCatNoSuchFileDetector tests the CatNoSuchFileDetector
func TestCatNoSuchFileDetector(t *testing.T) {
	detector, err := NewCatNoSuchFileDetector()
	if err != nil {
		t.Fatalf("Failed to create detector: %v", err)
	}

	examples := []DetectorExample{
		{
			Name:     "cat_missing_makefile",
			Input:    "cat: Makefile.in: No such file or directory",
			ClueType: "missing_file",
			Context:  map[string]string{"file_path": "Makefile.in"},
		},
		{
			Name:     "cat_missing_config",
			Input:    "cat: config.txt: No such file or directory",
			ClueType: "missing_file",
			Context:  map[string]string{"file_path": "config.txt"},
		},
	}

	for _, ex := range examples {
		t.Run(ex.Name, func(t *testing.T) {
			clues, err := detector.Detect(ex.Input, "")
			if err != nil {
				t.Fatalf("Detect() returned error: %v", err)
			}
			verifyClues(t, clues, ex)
		})
	}
}

// TestCCompilationErrorDetector tests the CCompilationErrorDetector
func TestCCompilationErrorDetector(t *testing.T) {
	detector, err := NewCCompilationErrorDetector()
	if err != nil {
		t.Fatalf("Failed to create detector: %v", err)
	}

	examples := []DetectorExample{
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
	}

	for _, ex := range examples {
		t.Run(ex.Name, func(t *testing.T) {
			clues, err := detector.Detect(ex.Input, "")
			if err != nil {
				t.Fatalf("Detect() returned error: %v", err)
			}
			verifyClues(t, clues, ex)
		})
	}
}

// TestCImplicitDeclarationDetector tests the CImplicitDeclarationDetector
func TestCImplicitDeclarationDetector(t *testing.T) {
	detector, err := NewCImplicitDeclarationDetector()
	if err != nil {
		t.Fatalf("Failed to create detector: %v", err)
	}

	examples := []DetectorExample{
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
	}

	for _, ex := range examples {
		t.Run(ex.Name, func(t *testing.T) {
			clues, err := detector.Detect(ex.Input, "")
			if err != nil {
				t.Fatalf("Detect() returned error: %v", err)
			}
			verifyClues(t, clues, ex)
		})
	}
}

// TestCIncompleteTypeDetector tests the CIncompleteTypeDetector
func TestCIncompleteTypeDetector(t *testing.T) {
	detector, err := NewCIncompleteTypeDetector()
	if err != nil {
		t.Fatalf("Failed to create detector: %v", err)
	}

	examples := []DetectorExample{
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
	}

	for _, ex := range examples {
		t.Run(ex.Name, func(t *testing.T) {
			clues, err := detector.Detect(ex.Input, "")
			if err != nil {
				t.Fatalf("Detect() returned error: %v", err)
			}
			verifyClues(t, clues, ex)
		})
	}
}

// TestCLinkerErrorDetector tests the CLinkerErrorDetector
func TestCLinkerErrorDetector(t *testing.T) {
	detector, err := NewCLinkerErrorDetector()
	if err != nil {
		t.Fatalf("Failed to create detector: %v", err)
	}

	examples := []DetectorExample{
		{
			Name:     "undefined_reference_backtick",
			Input:    "undefined reference to `ts_parser_new'",
			ClueType: "linker_undefined_symbols",
			Context:  map[string]string{"symbol": "ts_parser_new"},
		},
		{
			Name:     "undefined_reference_quote",
			Input:    "tree_print.c:(.text+0x137): undefined reference to 'ts_node_start_byte'",
			ClueType: "linker_undefined_symbols",
			Context:  map[string]string{"symbol": "ts_node_start_byte"},
		},
		{
			Name:     "ld_cannot_find",
			Input:    "/usr/bin/ld: cannot find exrecover.o: No such file or directory",
			ClueType: "missing_file",
			Context:  map[string]string{"file_path": "exrecover.o"},
		},
	}

	for _, ex := range examples {
		t.Run(ex.Name, func(t *testing.T) {
			clues, err := detector.Detect(ex.Input, "")
			if err != nil {
				t.Fatalf("Detect() returned error: %v", err)
			}
			verifyClues(t, clues, ex)
		})
	}
}

// TestCSyntaxErrorDetector tests the CSyntaxErrorDetector
func TestCSyntaxErrorDetector(t *testing.T) {
	detector, err := NewCSyntaxErrorDetector()
	if err != nil {
		t.Fatalf("Failed to create detector: %v", err)
	}

	examples := []DetectorExample{
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
	}

	for _, ex := range examples {
		t.Run(ex.Name, func(t *testing.T) {
			clues, err := detector.Detect(ex.Input, "")
			if err != nil {
				t.Fatalf("Detect() returned error: %v", err)
			}
			verifyClues(t, clues, ex)
		})
	}
}

// TestCUndeclaredIdentifierDetector tests the CUndeclaredIdentifierDetector
func TestCUndeclaredIdentifierDetector(t *testing.T) {
	detector, err := NewCUndeclaredIdentifierDetector()
	if err != nil {
		t.Fatalf("Failed to create detector: %v", err)
	}

	examples := []DetectorExample{
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
	}

	for _, ex := range examples {
		t.Run(ex.Name, func(t *testing.T) {
			clues, err := detector.Detect(ex.Input, "")
			if err != nil {
				t.Fatalf("Detect() returned error: %v", err)
			}
			verifyClues(t, clues, ex)
		})
	}
}

// TestCUnknownTypeDetector tests the CUnknownTypeDetector
func TestCUnknownTypeDetector(t *testing.T) {
	detector, err := NewCUnknownTypeDetector()
	if err != nil {
		t.Fatalf("Failed to create detector: %v", err)
	}

	examples := []DetectorExample{
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
	}

	for _, ex := range examples {
		t.Run(ex.Name, func(t *testing.T) {
			clues, err := detector.Detect(ex.Input, "")
			if err != nil {
				t.Fatalf("Detect() returned error: %v", err)
			}
			verifyClues(t, clues, ex)
		})
	}
}

// TestDiffNoSuchFileDetector tests the DiffNoSuchFileDetector
func TestDiffNoSuchFileDetector(t *testing.T) {
	detector, err := NewDiffNoSuchFileDetector()
	if err != nil {
		t.Fatalf("Failed to create detector: %v", err)
	}

	examples := []DetectorExample{
		{
			Name:     "diff_missing_file",
			Input:    "diff: expected.txt: No such file or directory",
			ClueType: "missing_file",
			Context:  map[string]string{"file_path": "expected.txt"},
		},
	}

	for _, ex := range examples {
		t.Run(ex.Name, func(t *testing.T) {
			clues, err := detector.Detect(ex.Input, "")
			if err != nil {
				t.Fatalf("Detect() returned error: %v", err)
			}
			verifyClues(t, clues, ex)
		})
	}
}

// TestFileNotFoundDetector tests the FileNotFoundDetector
func TestFileNotFoundDetector(t *testing.T) {
	detector, err := NewFileNotFoundDetector()
	if err != nil {
		t.Fatalf("Failed to create detector: %v", err)
	}

	examples := []DetectorExample{
		{
			Name:     "python_file_not_found",
			Input:    "FileNotFoundError: [Errno 2] No such file or directory: './test.sh'",
			ClueType: "missing_file",
			Context:  map[string]string{"file_path": "./test.sh"},
		},
		{
			Name:     "python_file_not_found_simple",
			Input:    "FileNotFoundError: ./configure",
			ClueType: "missing_file_simple",
			Context:  map[string]string{"file_path": "./configure"},
		},
	}

	for _, ex := range examples {
		t.Run(ex.Name, func(t *testing.T) {
			clues, err := detector.Detect(ex.Input, "")
			if err != nil {
				t.Fatalf("Detect() returned error: %v", err)
			}
			verifyClues(t, clues, ex)
		})
	}
}

// TestFopenNoSuchFileDetector tests the FopenNoSuchFileDetector
func TestFopenNoSuchFileDetector(t *testing.T) {
	detector, err := NewFopenNoSuchFileDetector()
	if err != nil {
		t.Fatalf("Failed to create detector: %v", err)
	}

	examples := []DetectorExample{
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
	}

	for _, ex := range examples {
		t.Run(ex.Name, func(t *testing.T) {
			clues, err := detector.Detect(ex.Input, "")
			if err != nil {
				t.Fatalf("Detect() returned error: %v", err)
			}
			verifyClues(t, clues, ex)
		})
	}
}

// TestMakeEnteringDirectoryDetector tests the MakeEnteringDirectoryDetector
func TestMakeEnteringDirectoryDetector(t *testing.T) {
	detector, err := NewMakeEnteringDirectoryDetector()
	if err != nil {
		t.Fatalf("Failed to create detector: %v", err)
	}

	examples := []DetectorExample{
		{
			Name:     "make_entering_simple",
			Input:    "make: Entering directory '/home/user/project'",
			ClueType: "make_enter_directory",
			Context:  map[string]string{"directory": "/home/user/project"},
		},
		{
			Name:     "make_entering_with_level",
			Input:    "make[1]: Entering directory '/tmp/build'",
			ClueType: "make_enter_directory",
			Context:  map[string]string{"directory": "/tmp/build"},
		},
	}

	for _, ex := range examples {
		t.Run(ex.Name, func(t *testing.T) {
			clues, err := detector.Detect(ex.Input, "")
			if err != nil {
				t.Fatalf("Detect() returned error: %v", err)
			}
			verifyClues(t, clues, ex)
		})
	}
}

// TestMakeGlobPatternErrorDetector tests the MakeGlobPatternErrorDetector
func TestMakeGlobPatternErrorDetector(t *testing.T) {
	detector, err := NewMakeGlobPatternErrorDetector()
	if err != nil {
		t.Fatalf("Failed to create detector: %v", err)
	}

	examples := []DetectorExample{
		{
			Name:     "make_glob_missing",
			Input:    "make: *** Makefile.inc: No such file or directory.  Stop.",
			ClueType: "missing_file",
			Context:  map[string]string{"file_path": "Makefile.inc"},
		},
	}

	for _, ex := range examples {
		t.Run(ex.Name, func(t *testing.T) {
			clues, err := detector.Detect(ex.Input, "")
			if err != nil {
				t.Fatalf("Detect() returned error: %v", err)
			}
			verifyClues(t, clues, ex)
		})
	}
}

// TestMakeMissingTargetDetector tests the MakeMissingTargetDetector
func TestMakeMissingTargetDetector(t *testing.T) {
	detector, err := NewMakeMissingTargetDetector()
	if err != nil {
		t.Fatalf("Failed to create detector: %v", err)
	}

	examples := []DetectorExample{
		{
			Name:     "make_missing_target",
			Input:    "No rule to make target 'utils.o', needed by 'main'",
			ClueType: "make_missing_target",
			Context: map[string]string{
				"target":    "utils.o",
				"needed_by": "main",
			},
		},
	}

	for _, ex := range examples {
		t.Run(ex.Name, func(t *testing.T) {
			clues, err := detector.Detect(ex.Input, "")
			if err != nil {
				t.Fatalf("Detect() returned error: %v", err)
			}
			verifyClues(t, clues, ex)
		})
	}
}

// TestMakeNoRuleDetector tests the MakeNoRuleDetector
func TestMakeNoRuleDetector(t *testing.T) {
	detector, err := NewMakeNoRuleDetector()
	if err != nil {
		t.Fatalf("Failed to create detector: %v", err)
	}

	examples := []DetectorExample{
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
	}

	for _, ex := range examples {
		t.Run(ex.Name, func(t *testing.T) {
			clues, err := detector.Detect(ex.Input, "")
			if err != nil {
				t.Fatalf("Detect() returned error: %v", err)
			}
			verifyClues(t, clues, ex)
		})
	}
}

// TestPermissionDeniedDetector tests the PermissionDeniedDetector
func TestPermissionDeniedDetector(t *testing.T) {
	detector, err := NewPermissionDeniedDetector()
	if err != nil {
		t.Fatalf("Failed to create detector: %v", err)
	}

	examples := []DetectorExample{
		{
			Name:     "python_permission_denied",
			Input:    "Permission denied: '/etc/passwd'",
			ClueType: "py_permission_denied",
			Context:  map[string]string{"file_path": "/etc/passwd"},
		},
		{
			Name:     "shell_permission_denied",
			Input:    "bash: /root/script.sh: Permission denied",
			ClueType: "sh_permission_denied",
			Context:  map[string]string{"file_path": "/root/script.sh"},
		},
	}

	for _, ex := range examples {
		t.Run(ex.Name, func(t *testing.T) {
			clues, err := detector.Detect(ex.Input, "")
			if err != nil {
				t.Fatalf("Detect() returned error: %v", err)
			}
			verifyClues(t, clues, ex)
		})
	}
}

// TestPythonNameErrorDetector tests the PythonNameErrorDetector
func TestPythonNameErrorDetector(t *testing.T) {
	detector, err := NewPythonNameErrorDetector()
	if err != nil {
		t.Fatalf("Failed to create detector: %v", err)
	}

	examples := []DetectorExample{
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
	}

	for _, ex := range examples {
		t.Run(ex.Name, func(t *testing.T) {
			clues, err := detector.Detect(ex.Input, "")
			if err != nil {
				t.Fatalf("Detect() returned error: %v", err)
			}
			verifyClues(t, clues, ex)
		})
	}
}

// TestShellCannotOpenDetector tests the ShellCannotOpenDetector
func TestShellCannotOpenDetector(t *testing.T) {
	detector, err := NewShellCannotOpenDetector()
	if err != nil {
		t.Fatalf("Failed to create detector: %v", err)
	}

	examples := []DetectorExample{
		{
			Name:     "shell_cannot_open",
			Input:    "sh: 1: cannot open config.sh: No such file",
			ClueType: "missing_file",
			Context:  map[string]string{"file_path": "config.sh"},
		},
	}

	for _, ex := range examples {
		t.Run(ex.Name, func(t *testing.T) {
			clues, err := detector.Detect(ex.Input, "")
			if err != nil {
				t.Fatalf("Detect() returned error: %v", err)
			}
			verifyClues(t, clues, ex)
		})
	}
}

// TestShellCommandNotFoundDetector tests the ShellCommandNotFoundDetector
func TestShellCommandNotFoundDetector(t *testing.T) {
	detector, err := NewShellCommandNotFoundDetector()
	if err != nil {
		t.Fatalf("Failed to create detector: %v", err)
	}

	examples := []DetectorExample{
		{
			Name:     "shell_no_such_file",
			Input:    "bash: line 5: ./run.sh: No such file or directory",
			ClueType: "missing_file",
			Context:  map[string]string{"file_path": "run.sh"},
		},
		{
			Name:     "shell_not_found",
			Input:    "sh: 1: ./script: not found",
			ClueType: "missing_file_not_found",
			Context:  map[string]string{"file_path": "script"},
		},
	}

	for _, ex := range examples {
		t.Run(ex.Name, func(t *testing.T) {
			clues, err := detector.Detect(ex.Input, "")
			if err != nil {
				t.Fatalf("Detect() returned error: %v", err)
			}
			verifyClues(t, clues, ex)
		})
	}
}

// TestTestFailureDetector tests the TestFailureDetector
func TestTestFailureDetector(t *testing.T) {
	detector, err := NewTestFailureDetector()
	if err != nil {
		t.Fatalf("Failed to create detector: %v", err)
	}

	examples := []DetectorExample{
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
	}

	for _, ex := range examples {
		t.Run(ex.Name, func(t *testing.T) {
			clues, err := detector.Detect(ex.Input, "")
			if err != nil {
				t.Fatalf("Detect() returned error: %v", err)
			}
			verifyClues(t, clues, ex)
		})
	}
}

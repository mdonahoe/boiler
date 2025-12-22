// All detector implementations for the boil pipeline
package detectors

import (
	"github.com/mdonahoe/boiler/src/boil/pipeline"
)

// CannotOpenFileDetector detects "Cannot open file" errors
type CannotOpenFileDetector struct {
	*BaseDetector
}

func NewCannotOpenFileDetector() (*CannotOpenFileDetector, error) {
	base, err := NewBaseDetector("CannotOpenFileDetector", 100, map[string]string{
		"missing_file": `[Ee]rror:?\s+Cannot open file\s+['"](?P<file_path>[^'"]+)['"]`,
	})
	if err != nil {
		return nil, err
	}
	return &CannotOpenFileDetector{base}, nil
}

// CatNoSuchFileDetector detects cat command "No such file" errors
type CatNoSuchFileDetector struct {
	*BaseDetector
}

func NewCatNoSuchFileDetector() (*CatNoSuchFileDetector, error) {
	base, err := NewBaseDetector("CatNoSuchFileDetector", 100, map[string]string{
		"missing_file": `cat:\s*(?P<file_path>[^\s:]+):\s*No such file or directory`,
	})
	if err != nil {
		return nil, err
	}
	return &CatNoSuchFileDetector{base}, nil
}

// CCompilationErrorDetector detects C/C++ compilation errors for missing files
type CCompilationErrorDetector struct {
	*BaseDetector
}

func NewCCompilationErrorDetector() (*CCompilationErrorDetector, error) {
	base, err := NewBaseDetector("CCompilationErrorDetector", 100, map[string]string{
		"missing_file": `fatal error:\s+\.?/?(?P<file_path>[^\s:]+):\s+No such file or directory`,
	})
	if err != nil {
		return nil, err
	}
	return &CCompilationErrorDetector{base}, nil
}

// CImplicitDeclarationDetector detects C implicit function declaration errors
type CImplicitDeclarationDetector struct {
	*BaseDetector
}

func NewCImplicitDeclarationDetector() (*CImplicitDeclarationDetector, error) {
	base, err := NewBaseDetector("CImplicitDeclarationDetector", 100, map[string]string{
		"missing_c_include": `(?P<file_path>[a-zA-Z0-9_./\-]+\.c):\d+:\d+:\s+(?:error|warning):\s+implicit declaration of function\s+[''](?P<function_name>[^'']+)[''].*?note:\s+include\s+['']<(?P<suggested_include>[^>]+)>['']`,
		"missing_c_function": `(?P<file_path>[a-zA-Z0-9_./\-]+\.c):(?P<line_number>\d+):\d+:\s+(?:error|warning):\s+implicit declaration of function\s+[''](?P<function_name>[^'']+)['']`,
	})
	if err != nil {
		return nil, err
	}
	return &CImplicitDeclarationDetector{base}, nil
}

// CIncompleteTypeDetector detects C incomplete type errors
type CIncompleteTypeDetector struct {
	*BaseDetector
}

func NewCIncompleteTypeDetector() (*CIncompleteTypeDetector, error) {
	base, err := NewBaseDetector("CIncompleteTypeDetector", 100, map[string]string{
		"missing_c_include": `(?P<file_path>[a-zA-Z0-9_./\-]+\.c):\d+:\d+:[^\n]*error:[^\n]*(?:has incomplete type|storage size).*struct\s+(?P<struct_name>termios|winsize|stat|tm|sigaction|dirent)`,
	})
	if err != nil {
		return nil, err
	}
	return &CIncompleteTypeDetector{base}, nil
}

// CLinkerErrorDetector detects C/C++ linker errors
type CLinkerErrorDetector struct {
	*BaseDetector
}

func NewCLinkerErrorDetector() (*CLinkerErrorDetector, error) {
	base, err := NewBaseDetector("CLinkerErrorDetector", 100, map[string]string{
		"linker_undefined_symbols": "undefined reference to [`'](?P<symbol>[^'`]+)[`']",
		"missing_file":             `/usr/bin/ld:.*?cannot find\s+(?P<file_path>[^\s:]+):\s+No such file or directory`,
	})
	if err != nil {
		return nil, err
	}
	return &CLinkerErrorDetector{base}, nil
}

// CSyntaxErrorDetector detects C/C++ syntax errors
type CSyntaxErrorDetector struct {
	*BaseDetector
}

func NewCSyntaxErrorDetector() (*CSyntaxErrorDetector, error) {
	base, err := NewBaseDetector("CSyntaxErrorDetector", 100, map[string]string{
		"c_syntax_error_in_header": `(?P<file_path>[^\s:]+\.h):(?P<line_number>\d+):\d+:\s+error:\s+expected\s+.+?\s+before\s+[''](?P<unexpected_token>[^'']+)['']`,
		"c_syntax_error_in_source": `(?P<file_path>[^\s:]+\.c):(?P<line_number>\d+):\d+:\s+error:\s+expected\s+.+?\s+before\s+[''](?P<unexpected_token>[^'']+)['']`,
	})
	if err != nil {
		return nil, err
	}
	return &CSyntaxErrorDetector{base}, nil
}

// CUndeclaredIdentifierDetector detects C undeclared identifier errors
type CUndeclaredIdentifierDetector struct {
	*BaseDetector
}

func NewCUndeclaredIdentifierDetector() (*CUndeclaredIdentifierDetector, error) {
	base, err := NewBaseDetector("CUndeclaredIdentifierDetector", 100, map[string]string{
		"missing_c_include":   `(?P<file_path>[a-zA-Z0-9_./\-]+\.c):\d+:\d+:[^\n]*undeclared.*note:.*is defined in header\s+['']<(?P<suggested_include>[^>]+)>['']`,
		"missing_c_function": `(?P<file_path>[a-zA-Z0-9_./\-]+\.c):(?P<line_number>\d+):\d+:\s+error:\s+[''](?P<identifier>[^'']+)['']\s+undeclared\s+\(first use`,
	})
	if err != nil {
		return nil, err
	}
	return &CUndeclaredIdentifierDetector{base}, nil
}

// CUnknownTypeDetector detects C unknown type name errors
type CUnknownTypeDetector struct {
	*BaseDetector
}

func NewCUnknownTypeDetector() (*CUnknownTypeDetector, error) {
	base, err := NewBaseDetector("CUnknownTypeDetector", 100, map[string]string{
		"unknown_type_name": `(?P<file_path>[a-zA-Z0-9_./\-]+\.c):(?P<line_number>\d+):\d+:\s+error:\s+unknown type name\s+[''](?P<type_name>[^'']+)['']`,
	})
	if err != nil {
		return nil, err
	}
	return &CUnknownTypeDetector{base}, nil
}

// DiffNoSuchFileDetector detects diff command "No such file" errors
type DiffNoSuchFileDetector struct {
	*BaseDetector
}

func NewDiffNoSuchFileDetector() (*DiffNoSuchFileDetector, error) {
	base, err := NewBaseDetector("DiffNoSuchFileDetector", 100, map[string]string{
		"missing_file": `diff:\s*(?P<file_path>[^\s:]+):\s*No such file or directory`,
	})
	if err != nil {
		return nil, err
	}
	return &DiffNoSuchFileDetector{base}, nil
}

// FileNotFoundDetector detects Python FileNotFoundError
type FileNotFoundDetector struct {
	*BaseDetector
}

func NewFileNotFoundDetector() (*FileNotFoundDetector, error) {
	base, err := NewBaseDetector("FileNotFoundDetector", 100, map[string]string{
		"missing_file":        `FileNotFoundError:.*?No such file or directory:\s*['"](?P<file_path>[^'"]+)['"]`,
		"missing_file_simple": `FileNotFoundError:\s*(?P<file_path>[^\s:]+)`,
	})
	if err != nil {
		return nil, err
	}
	return &FileNotFoundDetector{base}, nil
}

// FopenNoSuchFileDetector detects fopen "No such file" errors
type FopenNoSuchFileDetector struct {
	*BaseDetector
}

func NewFopenNoSuchFileDetector() (*FopenNoSuchFileDetector, error) {
	base, err := NewBaseDetector("FopenNoSuchFileDetector", 100, map[string]string{
		"missing_file":           `fopen:\s+(?P<file_path>[^\s:]+?):\s*No such file or directory`,
		"missing_file_assertion": `AssertionError:\s*['"](?P<file_path>[^'"]+\.(?:py|txt|md|c|h|cpp|hpp|json|yaml|yml|sh|rs|go|java|js|ts|html|css|xml|sql))['"].*fopen:\s*No such file or directory`,
	})
	if err != nil {
		return nil, err
	}
	return &FopenNoSuchFileDetector{base}, nil
}

// MakeEnteringDirectoryDetector detects make entering directory messages
type MakeEnteringDirectoryDetector struct {
	*BaseDetector
}

func NewMakeEnteringDirectoryDetector() (*MakeEnteringDirectoryDetector, error) {
	base, err := NewBaseDetector("MakeEnteringDirectoryDetector", 100, map[string]string{
		"make_enter_directory": `make(?:\[\d+\])?: Entering directory '(?P<directory>[^']+)'`,
	})
	if err != nil {
		return nil, err
	}
	return &MakeEnteringDirectoryDetector{base}, nil
}

// MakeGlobPatternErrorDetector detects make glob pattern errors
type MakeGlobPatternErrorDetector struct {
	*BaseDetector
}

func NewMakeGlobPatternErrorDetector() (*MakeGlobPatternErrorDetector, error) {
	base, err := NewBaseDetector("MakeGlobPatternErrorDetector", 100, map[string]string{
		"missing_file": `make(?:\[\d+\])?: \*\*\* (?P<file_path>[^:]+):\s+No such file or directory\.\s+Stop\.`,
	})
	if err != nil {
		return nil, err
	}
	return &MakeGlobPatternErrorDetector{base}, nil
}

// MakeMissingTargetDetector detects make missing target errors
type MakeMissingTargetDetector struct {
	*BaseDetector
}

func NewMakeMissingTargetDetector() (*MakeMissingTargetDetector, error) {
	base, err := NewBaseDetector("MakeMissingTargetDetector", 100, map[string]string{
		"make_missing_target": `No rule to make target '(?P<target>[^']+)', needed by '(?P<needed_by>[^']+)'`,
	})
	if err != nil {
		return nil, err
	}
	return &MakeMissingTargetDetector{base}, nil
}

// MakeNoRuleDetector detects make "No rule to make target" errors
type MakeNoRuleDetector struct {
	*BaseDetector
}

func NewMakeNoRuleDetector() (*MakeNoRuleDetector, error) {
	base, err := NewBaseDetector("MakeNoRuleDetector", 100, map[string]string{
		"make_no_rule": `make(?:\[\d+\])?: \*\*\* No rule to make target '(?P<target>[^']+)'\.\s+Stop\.`,
	})
	if err != nil {
		return nil, err
	}
	return &MakeNoRuleDetector{base}, nil
}

// PermissionDeniedDetector detects permission denied errors
type PermissionDeniedDetector struct {
	*BaseDetector
}

func NewPermissionDeniedDetector() (*PermissionDeniedDetector, error) {
	base, err := NewBaseDetector("PermissionDeniedDetector", 100, map[string]string{
		"py_permission_denied": `Permission denied:\s*['"]?(?P<file_path>[^'"]+)['"]?`,
		"sh_permission_denied": `:\s*(?P<file_path>[^:]+):\s*Permission denied`,
	})
	if err != nil {
		return nil, err
	}
	return &PermissionDeniedDetector{base}, nil
}

// PythonNameErrorDetector detects Python NameError exceptions
type PythonNameErrorDetector struct {
	*BaseDetector
}

func NewPythonNameErrorDetector() (*PythonNameErrorDetector, error) {
	base, err := NewBaseDetector("PythonNameErrorDetector", 100, map[string]string{
		"python_name_error": `File "(?P<file_path>[^"]+\.py)", line (?P<line_number>\d+),.*?NameError: (?:global )?name '(?P<undefined_name>\w+)' is not defined`,
	})
	if err != nil {
		return nil, err
	}
	return &PythonNameErrorDetector{base}, nil
}

// ShellCannotOpenDetector detects shell "cannot open" errors
type ShellCannotOpenDetector struct {
	*BaseDetector
}

func NewShellCannotOpenDetector() (*ShellCannotOpenDetector, error) {
	base, err := NewBaseDetector("ShellCannotOpenDetector", 100, map[string]string{
		"missing_file": `sh:\s*\d+:\s*cannot open\s+(?P<file_path>[^\s:]+):\s*No such file`,
	})
	if err != nil {
		return nil, err
	}
	return &ShellCannotOpenDetector{base}, nil
}

// ShellCommandNotFoundDetector detects shell command not found errors
type ShellCommandNotFoundDetector struct {
	*BaseDetector
}

func NewShellCommandNotFoundDetector() (*ShellCommandNotFoundDetector, error) {
	base, err := NewBaseDetector("ShellCommandNotFoundDetector", 100, map[string]string{
		"missing_file":           `:\s*line\s+\d+:\s*\.?/?(?P<file_path>[^\s:]+):\s*No such file or directory`,
		"missing_file_not_found": `:\s*\d+:\s*\.?/?(?P<file_path>[^\s:]+):\s*not found`,
	})
	if err != nil {
		return nil, err
	}
	return &ShellCommandNotFoundDetector{base}, nil
}

// TestFailureDetector detects test failure patterns
type TestFailureDetector struct {
	*BaseDetector
}

func NewTestFailureDetector() (*TestFailureDetector, error) {
	base, err := NewBaseDetector("TestFailureDetector", 100, map[string]string{
		"test_failure":                   `File\s+['"](?P<test_file>[^'"]+\.py)['"]\s*,\s+line\s+(?P<line_number>\d+),\s+in\s+(?P<test_name>\w+)`,
		"test_assertion_with_filename":   `AssertionError:\s*['"](?P<suspected_file>[^'"]+\.(?:py|txt|md|c|h|cpp|hpp|json|yaml|yml|sh))['"].*not found`,
		"c_test_failure":                 "(?P<test_file>[^\\s:]+\\.c):(?P<line_number>\\d+):\\s*(?P<test_name>\\w+):\\s*Assertion\\s*[`'](?P<assertion>[^'`]+)[`']\\s*failed",
		"test_docstring_with_missing_file": `Test that[^\n]*(?:can open|open)\s+(?P<suspected_file>(?:README\.md|[a-zA-Z0-9_-]+\.(?:c|h|cpp|hpp|py|txt|md|json|yaml|yml|sh|rs|go|java|js|ts))).*fopen:\s*No such file or directory`,
	})
	if err != nil {
		return nil, err
	}
	return &TestFailureDetector{base}, nil
}

// RegisterAllDetectors registers all detectors with the global registry
func RegisterAllDetectors() error {
	detectors := []func() (pipeline.Detector, error){
		func() (pipeline.Detector, error) { return NewCannotOpenFileDetector() },
		func() (pipeline.Detector, error) { return NewCatNoSuchFileDetector() },
		func() (pipeline.Detector, error) { return NewCCompilationErrorDetector() },
		func() (pipeline.Detector, error) { return NewCImplicitDeclarationDetector() },
		func() (pipeline.Detector, error) { return NewCIncompleteTypeDetector() },
		func() (pipeline.Detector, error) { return NewCLinkerErrorDetector() },
		func() (pipeline.Detector, error) { return NewCSyntaxErrorDetector() },
		func() (pipeline.Detector, error) { return NewCUndeclaredIdentifierDetector() },
		func() (pipeline.Detector, error) { return NewCUnknownTypeDetector() },
		func() (pipeline.Detector, error) { return NewDiffNoSuchFileDetector() },
		func() (pipeline.Detector, error) { return NewFileNotFoundDetector() },
		func() (pipeline.Detector, error) { return NewFopenNoSuchFileDetector() },
		func() (pipeline.Detector, error) { return NewMakeEnteringDirectoryDetector() },
		func() (pipeline.Detector, error) { return NewMakeGlobPatternErrorDetector() },
		func() (pipeline.Detector, error) { return NewMakeMissingTargetDetector() },
		func() (pipeline.Detector, error) { return NewMakeNoRuleDetector() },
		func() (pipeline.Detector, error) { return NewPermissionDeniedDetector() },
		func() (pipeline.Detector, error) { return NewPythonNameErrorDetector() },
		func() (pipeline.Detector, error) { return NewShellCannotOpenDetector() },
		func() (pipeline.Detector, error) { return NewShellCommandNotFoundDetector() },
		func() (pipeline.Detector, error) { return NewTestFailureDetector() },
	}

	for _, createDetector := range detectors {
		detector, err := createDetector()
		if err != nil {
			return err
		}
		pipeline.RegisterDetector(detector)
	}

	return nil
}

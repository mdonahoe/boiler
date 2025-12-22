// Registration of all detectors.
package detectors

import (
	"github.com/mdonahoe/boiler/src/boil/pipeline"
)

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

// AllDetectorFactories returns factories for all detectors, used by tests
// to iterate over detectors and their examples.
func AllDetectorFactories() []func() (*BaseDetector, error) {
	return []func() (*BaseDetector, error){
		func() (*BaseDetector, error) { d, e := NewCannotOpenFileDetector(); return d.BaseDetector, e },
		func() (*BaseDetector, error) { d, e := NewCatNoSuchFileDetector(); return d.BaseDetector, e },
		func() (*BaseDetector, error) { d, e := NewCCompilationErrorDetector(); return d.BaseDetector, e },
		func() (*BaseDetector, error) { d, e := NewCImplicitDeclarationDetector(); return d.BaseDetector, e },
		func() (*BaseDetector, error) { d, e := NewCIncompleteTypeDetector(); return d.BaseDetector, e },
		func() (*BaseDetector, error) { d, e := NewCLinkerErrorDetector(); return d.BaseDetector, e },
		func() (*BaseDetector, error) { d, e := NewCSyntaxErrorDetector(); return d.BaseDetector, e },
		func() (*BaseDetector, error) { d, e := NewCUndeclaredIdentifierDetector(); return d.BaseDetector, e },
		func() (*BaseDetector, error) { d, e := NewCUnknownTypeDetector(); return d.BaseDetector, e },
		func() (*BaseDetector, error) { d, e := NewDiffNoSuchFileDetector(); return d.BaseDetector, e },
		func() (*BaseDetector, error) { d, e := NewFileNotFoundDetector(); return d.BaseDetector, e },
		func() (*BaseDetector, error) { d, e := NewFopenNoSuchFileDetector(); return d.BaseDetector, e },
		func() (*BaseDetector, error) { d, e := NewMakeEnteringDirectoryDetector(); return d.BaseDetector, e },
		func() (*BaseDetector, error) { d, e := NewMakeGlobPatternErrorDetector(); return d.BaseDetector, e },
		func() (*BaseDetector, error) { d, e := NewMakeMissingTargetDetector(); return d.BaseDetector, e },
		func() (*BaseDetector, error) { d, e := NewMakeNoRuleDetector(); return d.BaseDetector, e },
		func() (*BaseDetector, error) { d, e := NewPermissionDeniedDetector(); return d.BaseDetector, e },
		func() (*BaseDetector, error) { d, e := NewPythonNameErrorDetector(); return d.BaseDetector, e },
		func() (*BaseDetector, error) { d, e := NewShellCannotOpenDetector(); return d.BaseDetector, e },
		func() (*BaseDetector, error) { d, e := NewShellCommandNotFoundDetector(); return d.BaseDetector, e },
		func() (*BaseDetector, error) { d, e := NewTestFailureDetector(); return d.BaseDetector, e },
	}
}

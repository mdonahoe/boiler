// Registration of all detectors from JSON definitions.
package detectors

import (
	"github.com/mdonahoe/boiler/src/boil/pipeline"
)

// RegisterAllDetectors registers all detectors from JSON with the global registry
func RegisterAllDetectors() error {
	return RegisterJSONDetectors()
}

// AllDetectorFactories returns factories for all detectors, used by tests
// to iterate over detectors and their examples.
func AllDetectorFactories() ([]*BaseDetector, error) {
	detectors, err := LoadDetectorsFromJSON()
	if err != nil {
		return nil, err
	}

	var baseDetectors []*BaseDetector
	for _, d := range detectors {
		if jd, ok := d.(*JSONDetector); ok {
			baseDetectors = append(baseDetectors, jd.BaseDetector)
		}
	}
	return baseDetectors, nil
}

// GetDetectorByName returns a detector by name (for backwards compatibility)
func GetDetectorByName(name string) (pipeline.Detector, error) {
	detectors, err := LoadDetectorsFromJSON()
	if err != nil {
		return nil, err
	}
	for _, d := range detectors {
		if d.Name() == name {
			return d, nil
		}
	}
	return nil, nil
}

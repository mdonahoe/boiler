// JSON-based detector loading for data-driven error detection
package detectors

import (
	"embed"
	"encoding/json"
	"fmt"

	"github.com/mdonahoe/boiler/src/boil/pipeline"
)

//go:embed detectors.json
var detectorsJSON embed.FS

// DetectorDefinition represents a detector defined in JSON
type DetectorDefinition struct {
	Name     string              `json:"name"`
	Priority int                 `json:"priority"`
	Patterns map[string]string   `json:"patterns"`
	Examples []DetectorExampleDef `json:"examples"`
}

// DetectorExampleDef represents an example in JSON format
type DetectorExampleDef struct {
	Name     string            `json:"name"`
	Input    string            `json:"input"`
	ClueType string            `json:"clue_type"`
	Context  map[string]string `json:"context"`
}

// DetectorsFile represents the JSON file structure
type DetectorsFile struct {
	Detectors []DetectorDefinition `json:"detectors"`
}

// JSONDetector wraps a BaseDetector loaded from JSON
type JSONDetector struct {
	*BaseDetector
}

// LoadDetectorsFromJSON loads all detectors from the embedded JSON file
func LoadDetectorsFromJSON() ([]pipeline.Detector, error) {
	data, err := detectorsJSON.ReadFile("detectors.json")
	if err != nil {
		return nil, fmt.Errorf("failed to read embedded detectors.json: %w", err)
	}

	return LoadDetectorsFromJSONBytes(data)
}

// LoadDetectorsFromJSONBytes loads detectors from JSON bytes
func LoadDetectorsFromJSONBytes(data []byte) ([]pipeline.Detector, error) {
	var file DetectorsFile
	if err := json.Unmarshal(data, &file); err != nil {
		return nil, fmt.Errorf("failed to parse detectors JSON: %w", err)
	}

	var detectors []pipeline.Detector
	for _, def := range file.Detectors {
		detector, err := createDetectorFromDefinition(def)
		if err != nil {
			return nil, fmt.Errorf("failed to create detector %s: %w", def.Name, err)
		}
		detectors = append(detectors, detector)
	}

	return detectors, nil
}

// createDetectorFromDefinition creates a BaseDetector from a JSON definition
func createDetectorFromDefinition(def DetectorDefinition) (*JSONDetector, error) {
	// Convert examples from JSON format to DetectorExample
	examples := make([]DetectorExample, len(def.Examples))
	for i, ex := range def.Examples {
		examples[i] = DetectorExample{
			Name:     ex.Name,
			Input:    ex.Input,
			ClueType: ex.ClueType,
			Context:  ex.Context,
		}
	}

	base, err := NewBaseDetector(def.Name, def.Priority, def.Patterns, examples)
	if err != nil {
		return nil, err
	}

	return &JSONDetector{base}, nil
}

// RegisterJSONDetectors loads and registers all JSON-defined detectors
func RegisterJSONDetectors() error {
	detectors, err := LoadDetectorsFromJSON()
	if err != nil {
		return err
	}

	registry := pipeline.GetDetectorRegistry()
	for _, d := range detectors {
		registry.Register(d)
	}

	return nil
}

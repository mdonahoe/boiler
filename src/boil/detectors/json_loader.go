// JSON-based detector loading for data-driven error detection
package detectors

import (
	"embed"
	"encoding/json"
	"fmt"
	"path/filepath"
	"sort"

	"github.com/mdonahoe/boiler/src/boil/pipeline"
)

//go:embed definitions/*.json
var detectorsFS embed.FS

// DetectorDefinition represents a detector defined in JSON
type DetectorDefinition struct {
	Name     string               `json:"name"`
	Priority int                  `json:"priority"`
	Patterns map[string]string    `json:"patterns"`
	Examples []DetectorExampleDef `json:"examples"`
}

// DetectorExampleDef represents an example in JSON format
type DetectorExampleDef struct {
	Name     string            `json:"name"`
	Input    string            `json:"input"`
	ClueType string            `json:"clue_type"`
	Context  map[string]string `json:"context"`
}

// JSONDetector wraps a BaseDetector loaded from JSON
type JSONDetector struct {
	*BaseDetector
}

// LoadDetectorsFromJSON loads all detectors from the embedded JSON files in definitions/
func LoadDetectorsFromJSON() ([]pipeline.Detector, error) {
	entries, err := detectorsFS.ReadDir("definitions")
	if err != nil {
		return nil, fmt.Errorf("failed to read definitions directory: %w", err)
	}

	// Sort entries for consistent ordering
	sort.Slice(entries, func(i, j int) bool {
		return entries[i].Name() < entries[j].Name()
	})

	var detectors []pipeline.Detector
	for _, entry := range entries {
		if entry.IsDir() || filepath.Ext(entry.Name()) != ".json" {
			continue
		}

		data, err := detectorsFS.ReadFile(filepath.Join("definitions", entry.Name()))
		if err != nil {
			return nil, fmt.Errorf("failed to read %s: %w", entry.Name(), err)
		}

		detector, err := LoadDetectorFromJSONBytes(data)
		if err != nil {
			return nil, fmt.Errorf("failed to load detector from %s: %w", entry.Name(), err)
		}
		detectors = append(detectors, detector)
	}

	return detectors, nil
}

// LoadDetectorFromJSONBytes loads a single detector from JSON bytes
func LoadDetectorFromJSONBytes(data []byte) (pipeline.Detector, error) {
	var def DetectorDefinition
	if err := json.Unmarshal(data, &def); err != nil {
		return nil, fmt.Errorf("failed to parse detector JSON: %w", err)
	}

	return createDetectorFromDefinition(def)
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

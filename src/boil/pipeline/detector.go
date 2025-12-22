// Detector interface and registry for Stage 1: Error Detection
package pipeline

import (
	"fmt"
	"os"
	"sort"
	"strings"
)

// Detector analyzes stderr/stdout and produces ErrorClue objects
type Detector interface {
	// Name returns the human-readable name of this detector
	Name() string

	// Priority returns the priority for running this detector (lower = higher priority)
	// Most detectors should use priority 100
	Priority() int

	// Detect analyzes stderr and stdout to find error clues
	Detect(stderr, stdout string) ([]*ErrorClue, error)
}

// DetectorRegistry manages all error detectors
type DetectorRegistry struct {
	detectors []Detector
}

// NewDetectorRegistry creates a new detector registry
func NewDetectorRegistry() *DetectorRegistry {
	return &DetectorRegistry{
		detectors: make([]Detector, 0),
	}
}

// Register adds a detector to the registry
func (r *DetectorRegistry) Register(detector Detector) {
	r.detectors = append(r.detectors, detector)
	// Sort by priority (lower = higher priority)
	sort.Slice(r.detectors, func(i, j int) bool {
		return r.detectors[i].Priority() < r.detectors[j].Priority()
	})
}

// DetectAll runs all detectors and returns all ErrorClue objects found
func (r *DetectorRegistry) DetectAll(stderr, stdout string) ([]*ErrorClue, error) {
	var allClues []*ErrorClue

	// Check for verbose mode
	verbose := isVerbose()

	for _, detector := range r.detectors {
		clues, err := detector.Detect(stderr, stdout)
		if err != nil {
			if verbose {
				fmt.Printf("[Detector:%s] Error: %v\n", detector.Name(), err)
			}
			// Continue with other detectors
			continue
		}

		if len(clues) > 0 {
			if verbose {
				fmt.Printf("[Detector:%s] Found %d clue(s)\n", detector.Name(), len(clues))
			}
			allClues = append(allClues, clues...)
		}
	}

	return allClues, nil
}

// ListDetectors returns list of registered detector names
func (r *DetectorRegistry) ListDetectors() []string {
	names := make([]string, len(r.detectors))
	for i, d := range r.detectors {
		names[i] = d.Name()
	}
	return names
}

// Global registry instance
var globalDetectorRegistry = NewDetectorRegistry()

// RegisterDetector registers a detector with the global registry
func RegisterDetector(detector Detector) {
	globalDetectorRegistry.Register(detector)
}

// GetDetectorRegistry returns the global detector registry
func GetDetectorRegistry() *DetectorRegistry {
	return globalDetectorRegistry
}

// isVerbose checks if BOIL_VERBOSE environment variable is set
func isVerbose() bool {
	verbose := strings.ToLower(os.Getenv("BOIL_VERBOSE"))
	return verbose == "1" || verbose == "true" || verbose == "yes"
}

// IsVerbose is the public version of isVerbose
func IsVerbose() bool {
	return isVerbose()
}

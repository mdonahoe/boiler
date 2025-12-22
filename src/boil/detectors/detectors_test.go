// Unit tests for detector implementations.
//
// Tests iterate over all detectors and their embedded examples to verify
// that patterns correctly match error messages and extract expected context.
package detectors

import (
	"testing"

	"github.com/mdonahoe/boiler/src/boil/pipeline"
)

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

// TestAllDetectors runs all detector examples defined alongside their patterns.
// This ensures examples stay in sync with patterns and makes tests more readable.
func TestAllDetectors(t *testing.T) {
	for _, factory := range AllDetectorFactories() {
		detector, err := factory()
		if err != nil {
			t.Fatalf("Failed to create detector: %v", err)
		}

		t.Run(detector.Name(), func(t *testing.T) {
			examples := detector.Examples()
			if len(examples) == 0 {
				t.Errorf("Detector %s has no examples", detector.Name())
				return
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
		})
	}
}

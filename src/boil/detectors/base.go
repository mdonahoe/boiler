// Base classes for Stage 1: Error Detection
//
// Detectors analyze stderr/stdout and produce ErrorClue objects.
package detectors

import (
	"regexp"

	"github.com/mdonahoe/boiler/src/boil/pipeline"
)

// DetectorExample represents a test case for a detector.
// Each detector defines examples next to its patterns for readability.
type DetectorExample struct {
	Name     string            // Human-readable name for the test case
	Input    string            // Error text to match against
	ClueType string            // Expected clue type
	Context  map[string]string // Expected context values
}

// BaseDetector provides regex-based detection for most detectors
//
// Subclasses should define:
// - name: detector name
// - priority: execution priority (lower = higher priority, default 100)
// - patterns: map of pattern names to compiled regexes
// - examples: test cases for verification
//
// The Detect() method automatically:
// 1. Combines stderr and stdout
// 2. Searches for all patterns
// 3. Converts matches to ErrorClue objects using named capture groups
type BaseDetector struct {
	name     string
	priority int
	patterns map[string]*regexp.Regexp
	examples []DetectorExample
}

// NewBaseDetector creates a new regex-based detector
//
// Args:
//
//	name: Human-readable detector name
//	priority: Execution priority (lower = higher priority)
//	patterns: Map of pattern name to regex string (must use named groups)
//	examples: Test cases for verification (defined alongside patterns)
func NewBaseDetector(name string, priority int, patterns map[string]string, examples []DetectorExample) (*BaseDetector, error) {
	compiled := make(map[string]*regexp.Regexp)
	for patternName, pattern := range patterns {
		re, err := regexp.Compile(pattern)
		if err != nil {
			return nil, err
		}
		compiled[patternName] = re
	}

	return &BaseDetector{
		name:     name,
		priority: priority,
		patterns: compiled,
		examples: examples,
	}, nil
}

// Examples returns the test cases for this detector
func (d *BaseDetector) Examples() []DetectorExample {
	return d.examples
}

// Name returns the detector name
func (d *BaseDetector) Name() string {
	return d.name
}

// Priority returns the execution priority
func (d *BaseDetector) Priority() int {
	return d.priority
}

// Detect finds errors using regex patterns
//
// Combines stderr and stdout, then searches for all patterns.
// Converts regex matches to ErrorClue objects using named capture groups.
func (d *BaseDetector) Detect(stderr, stdout string) ([]*pipeline.ErrorClue, error) {
	combined := stderr + "\n" + stdout
	var clues []*pipeline.ErrorClue

	for patternName, re := range d.patterns {
		matches := re.FindAllStringSubmatch(combined, -1)
		for _, match := range matches {
			clue := d.matchToClue(patternName, match, re.SubexpNames())
			if clue != nil {
				clues = append(clues, clue)
			}
		}
	}

	return clues, nil
}

// matchToClue converts a regex match to an ErrorClue
//
// Extracts named groups from the regex match and creates a context map.
func (d *BaseDetector) matchToClue(patternName string, match []string, names []string) *pipeline.ErrorClue {
	if len(match) == 0 {
		return nil
	}

	// Build context from named groups
	context := make(map[string]string)
	for i, name := range names {
		if name != "" && i < len(match) {
			context[name] = match[i]
		}
	}

	return &pipeline.ErrorClue{
		ClueType:   patternName,
		Confidence: 1.0,
		Context:    context,
		SourceLine: match[0], // Full match is the source line
	}
}

package planners

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/mdonahoe/boiler/src/boil/pipeline"
)

func TestExtractFileReferences(t *testing.T) {
	// Create a temporary test file
	tmpDir := t.TempDir()
	testFile := filepath.Join(tmpDir, "test_dim.py")

	// Write content mimicking the real test file
	content := `def test_syntax_highlighting_c(self):
        """Test that C syntax highlighting works with color codes."""
        # Open example.c and wait for it to render
        input_str = "[sleep:50][ctrl-q]"
        input_tokens = parse_input_string(input_str)

        result = run_with_pty(
            command=["./dim", "example.c"],
            input_tokens=input_tokens,
            delay_ms=10,
            timeout=0.5,
            rows=24,
            cols=80
        )

        # Check that C content is visible
        self.assertIn("int main", result.output, "Expected to see main function")
        self.assertIn("#include", result.output, "Expected to see include directive")
`
	err := os.WriteFile(testFile, []byte(content), 0644)
	if err != nil {
		t.Fatalf("Failed to write test file: %v", err)
	}

	// Test extractFileReferences - line 17 is where assertIn is (simulating line 375)
	// Actually our content is shorter, let's use line 8 (the command line)
	refs := extractFileReferences(testFile, 8)

	// Should find example.c
	found := false
	for _, ref := range refs {
		if ref == "example.c" {
			found = true
			break
		}
	}
	if !found {
		t.Errorf("extractFileReferences did not find 'example.c' in test file. Got: %v", refs)
	}
}

func TestExtractFileReferencesFromAssertions(t *testing.T) {
	tmpDir := t.TempDir()
	testFile := filepath.Join(tmpDir, "test_example.py")

	content := `def test_file_exists(self):
        self.assertIn("config.json", result.output)
        self.assertEqual("data.txt", contents)
`
	err := os.WriteFile(testFile, []byte(content), 0644)
	if err != nil {
		t.Fatalf("Failed to write test file: %v", err)
	}

	refs := extractFileReferences(testFile, 2)

	// Should find config.json and data.txt
	refSet := make(map[string]bool)
	for _, ref := range refs {
		refSet[ref] = true
	}

	if !refSet["config.json"] {
		t.Errorf("extractFileReferences did not find 'config.json'. Got: %v", refs)
	}
	if !refSet["data.txt"] {
		t.Errorf("extractFileReferences did not find 'data.txt'. Got: %v", refs)
	}
}

func TestTestFailurePlannerWithFileReferences(t *testing.T) {
	// Create a temporary test file
	tmpDir := t.TempDir()
	testFile := filepath.Join(tmpDir, "test_dim.py")

	content := `def test_syntax_highlighting_c(self):
        """Test that C syntax highlighting works with color codes."""
        result = run_with_pty(
            command=["./dim", "example.c"],
            input_tokens=input_tokens,
        )
        self.assertIn("int main", result.output)
`
	err := os.WriteFile(testFile, []byte(content), 0644)
	if err != nil {
		t.Fatalf("Failed to write test file: %v", err)
	}

	// Create a test_failure clue
	clue := &pipeline.ErrorClue{
		ClueType:   "test_failure",
		Confidence: 1.0,
		Context: map[string]string{
			"test_file":   testFile,
			"line_number": "7",
			"test_name":   "test_syntax_highlighting_c",
		},
	}

	// Create GitState with example.c as deleted
	gitState := &pipeline.GitState{
		Ref:          "HEAD",
		DeletedFiles: []string{"example.c"},
		GitToplevel:  tmpDir,
	}

	// Create planner and generate plans
	planner := NewTestFailurePlanner()
	plans, err := planner.Plan([]*pipeline.ErrorClue{clue}, gitState)
	if err != nil {
		t.Fatalf("Planner failed: %v", err)
	}

	// Should generate a plan to restore example.c
	found := false
	for _, plan := range plans {
		if plan.TargetFile == "example.c" {
			found = true
			break
		}
	}
	if !found {
		t.Errorf("TestFailurePlanner did not generate plan for 'example.c'. Plans: %+v", plans)
	}
}

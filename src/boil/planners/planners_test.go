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

func TestExtractFileReferencesMultiLine(t *testing.T) {
	tmpDir := t.TempDir()
	testFile := filepath.Join(tmpDir, "test_multiline.py")

	// Test multi-line command definitions spanning several lines
	content := `def test_multiline_command(self):
        result = run_with_pty(
            command=[
                "./dim",
                "config.json"
            ],
            input_tokens=tokens,
        )
        self.assertIn("success", result.output)
`
	err := os.WriteFile(testFile, []byte(content), 0644)
	if err != nil {
		t.Fatalf("Failed to write test file: %v", err)
	}

	refs := extractFileReferences(testFile, 5)

	found := false
	for _, ref := range refs {
		if ref == "config.json" {
			found = true
			break
		}
	}
	if !found {
		t.Errorf("extractFileReferences did not find 'config.json' in multi-line command. Got: %v", refs)
	}
}

func TestExtractFileReferencesOpenCall(t *testing.T) {
	tmpDir := t.TempDir()
	testFile := filepath.Join(tmpDir, "test_open.py")

	content := `def test_open_file(self):
        with open("README.md") as f:
            contents = f.read()
        with open('settings.json', 'r') as f:
            data = json.load(f)
`
	err := os.WriteFile(testFile, []byte(content), 0644)
	if err != nil {
		t.Fatalf("Failed to write test file: %v", err)
	}

	refs := extractFileReferences(testFile, 3)

	refSet := make(map[string]bool)
	for _, ref := range refs {
		refSet[ref] = true
	}

	if !refSet["README.md"] {
		t.Errorf("extractFileReferences did not find 'README.md'. Got: %v", refs)
	}
	if !refSet["settings.json"] {
		t.Errorf("extractFileReferences did not find 'settings.json'. Got: %v", refs)
	}
}

func TestExtractFileReferencesEmptyFile(t *testing.T) {
	tmpDir := t.TempDir()
	testFile := filepath.Join(tmpDir, "test_empty.py")

	// Empty file
	err := os.WriteFile(testFile, []byte(""), 0644)
	if err != nil {
		t.Fatalf("Failed to write test file: %v", err)
	}

	refs := extractFileReferences(testFile, 1)

	if len(refs) != 0 {
		t.Errorf("extractFileReferences should return empty for empty file. Got: %v", refs)
	}
}

func TestExtractFileReferencesNonExistentFile(t *testing.T) {
	refs := extractFileReferences("/nonexistent/path/to/file.py", 1)

	if refs != nil {
		t.Errorf("extractFileReferences should return nil for non-existent file. Got: %v", refs)
	}
}

func TestExtractFileReferencesLineNumberBoundary(t *testing.T) {
	tmpDir := t.TempDir()
	testFile := filepath.Join(tmpDir, "test_boundary.py")

	content := `line1
line2
command=["./dim", "early.txt"]
line4
line5
line6
line7
line8
line9
line10
line11
line12
line13
line14
line15
line16
line17
line18
line19
line20
line21
line22
line23
line24
line25
command=["./dim", "late.txt"]
line27
`
	err := os.WriteFile(testFile, []byte(content), 0644)
	if err != nil {
		t.Fatalf("Failed to write test file: %v", err)
	}

	// Test with line number at the start - should find early.txt (within 20 lines after)
	refs := extractFileReferences(testFile, 1)
	refSet := make(map[string]bool)
	for _, ref := range refs {
		refSet[ref] = true
	}
	if !refSet["early.txt"] {
		t.Errorf("extractFileReferences at line 1 should find 'early.txt'. Got: %v", refs)
	}

	// Test with line number near the end - should find late.txt (within 10 lines before)
	refs2 := extractFileReferences(testFile, 27)
	refSet2 := make(map[string]bool)
	for _, ref := range refs2 {
		refSet2[ref] = true
	}
	if !refSet2["late.txt"] {
		t.Errorf("extractFileReferences at line 27 should find 'late.txt'. Got: %v", refs2)
	}
}

func TestExtractFileReferencesCStringLiterals(t *testing.T) {
	tmpDir := t.TempDir()
	testFile := filepath.Join(tmpDir, "test_c.c")

	content := `int main() {
    FILE *f = fopen("data.txt", "r");
    char *path = "./config.json";
    process("input.yaml");
    return 0;
}
`
	err := os.WriteFile(testFile, []byte(content), 0644)
	if err != nil {
		t.Fatalf("Failed to write test file: %v", err)
	}

	refs := extractFileReferences(testFile, 3)

	refSet := make(map[string]bool)
	for _, ref := range refs {
		refSet[ref] = true
	}

	if !refSet["data.txt"] {
		t.Errorf("extractFileReferences did not find 'data.txt'. Got: %v", refs)
	}
	if !refSet["config.json"] {
		t.Errorf("extractFileReferences did not find 'config.json'. Got: %v", refs)
	}
	if !refSet["input.yaml"] {
		t.Errorf("extractFileReferences did not find 'input.yaml'. Got: %v", refs)
	}
}

func TestExtractFileReferencesNoMatches(t *testing.T) {
	tmpDir := t.TempDir()
	testFile := filepath.Join(tmpDir, "test_no_matches.py")

	content := `def test_something(self):
        x = 1 + 2
        y = "hello world"
        self.assertEqual(x, 3)
`
	err := os.WriteFile(testFile, []byte(content), 0644)
	if err != nil {
		t.Fatalf("Failed to write test file: %v", err)
	}

	refs := extractFileReferences(testFile, 2)

	if len(refs) != 0 {
		t.Errorf("extractFileReferences should return empty when no file references. Got: %v", refs)
	}
}

func TestExtractFileReferencesNestedCalls(t *testing.T) {
	tmpDir := t.TempDir()
	testFile := filepath.Join(tmpDir, "test_nested.py")

	// Deeply nested function calls
	content := `def test_nested(self):
        result = process(
            load(
                parse(
                    open("nested.json").read()
                )
            )
        )
        self.assertIn("key", result)
`
	err := os.WriteFile(testFile, []byte(content), 0644)
	if err != nil {
		t.Fatalf("Failed to write test file: %v", err)
	}

	refs := extractFileReferences(testFile, 5)

	found := false
	for _, ref := range refs {
		if ref == "nested.json" {
			found = true
			break
		}
	}
	if !found {
		t.Errorf("extractFileReferences did not find 'nested.json' in nested calls. Got: %v", refs)
	}
}

func TestExtractFileReferencesZeroLineNumber(t *testing.T) {
	tmpDir := t.TempDir()
	testFile := filepath.Join(tmpDir, "test_zero.py")

	content := `command=["./dim", "first.txt"]
second line
`
	err := os.WriteFile(testFile, []byte(content), 0644)
	if err != nil {
		t.Fatalf("Failed to write test file: %v", err)
	}

	// Line number 0 should be handled gracefully (treated as line 1)
	refs := extractFileReferences(testFile, 0)

	// Should still find first.txt since context starts from line 0
	found := false
	for _, ref := range refs {
		if ref == "first.txt" {
			found = true
			break
		}
	}
	if !found {
		t.Errorf("extractFileReferences with line 0 should find 'first.txt'. Got: %v", refs)
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

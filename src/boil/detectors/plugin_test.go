// Tests for detector plugin loading
package detectors

import (
	"os"
	"path/filepath"
	"testing"
)

// TestLoadDetectorPlugins_NoDirectory tests that missing plugins dir is not an error
func TestLoadDetectorPlugins_NoDirectory(t *testing.T) {
	// Change to a temp directory with no plugins
	origDir, _ := os.Getwd()
	tmpDir := t.TempDir()
	os.Chdir(tmpDir)
	defer os.Chdir(origDir)

	detectors, err := LoadDetectorPlugins()
	if err != nil {
		t.Fatalf("LoadDetectorPlugins() returned error: %v", err)
	}
	if len(detectors) != 0 {
		t.Errorf("Expected 0 detectors, got %d", len(detectors))
	}
}

// TestLoadDetectorPlugins_ValidPlugin tests loading a valid JSON plugin
func TestLoadDetectorPlugins_ValidPlugin(t *testing.T) {
	// Create temp directory structure
	origDir, _ := os.Getwd()
	tmpDir := t.TempDir()
	os.Chdir(tmpDir)
	defer os.Chdir(origDir)

	// Create plugins directory
	pluginsDir := filepath.Join(".boil", "plugins", "detectors")
	if err := os.MkdirAll(pluginsDir, 0755); err != nil {
		t.Fatalf("Failed to create plugins dir: %v", err)
	}

	// Write a valid detector plugin
	pluginJSON := `{
		"name": "TestPluginDetector",
		"priority": 100,
		"patterns": {
			"test_plugin_error": "plugin error: (?P<message>.+)"
		},
		"examples": [
			{
				"name": "test_plugin_error",
				"input": "plugin error: something went wrong",
				"clue_type": "test_plugin_error",
				"context": {"message": "something went wrong"}
			}
		]
	}`
	pluginPath := filepath.Join(pluginsDir, "test_plugin.json")
	if err := os.WriteFile(pluginPath, []byte(pluginJSON), 0644); err != nil {
		t.Fatalf("Failed to write plugin file: %v", err)
	}

	// Load plugins
	detectors, err := LoadDetectorPlugins()
	if err != nil {
		t.Fatalf("LoadDetectorPlugins() returned error: %v", err)
	}

	if len(detectors) != 1 {
		t.Fatalf("Expected 1 detector, got %d", len(detectors))
	}

	if detectors[0].Name() != "TestPluginDetector" {
		t.Errorf("Expected detector name 'TestPluginDetector', got %q", detectors[0].Name())
	}

	// Test that the detector works
	clues, err := detectors[0].Detect("plugin error: something went wrong", "")
	if err != nil {
		t.Fatalf("Detect() returned error: %v", err)
	}
	if len(clues) != 1 {
		t.Fatalf("Expected 1 clue, got %d", len(clues))
	}
	if clues[0].ClueType != "test_plugin_error" {
		t.Errorf("Expected clue type 'test_plugin_error', got %q", clues[0].ClueType)
	}
	if clues[0].Context["message"] != "something went wrong" {
		t.Errorf("Expected message 'something went wrong', got %q", clues[0].Context["message"])
	}
}

// TestLoadDetectorPlugins_SkipsUnderscore tests that files starting with _ are skipped
func TestLoadDetectorPlugins_SkipsUnderscore(t *testing.T) {
	origDir, _ := os.Getwd()
	tmpDir := t.TempDir()
	os.Chdir(tmpDir)
	defer os.Chdir(origDir)

	pluginsDir := filepath.Join(".boil", "plugins", "detectors")
	if err := os.MkdirAll(pluginsDir, 0755); err != nil {
		t.Fatalf("Failed to create plugins dir: %v", err)
	}

	// Write a disabled plugin (starts with underscore)
	pluginJSON := `{"name": "DisabledDetector", "priority": 100, "patterns": {}, "examples": []}`
	pluginPath := filepath.Join(pluginsDir, "_disabled.json")
	if err := os.WriteFile(pluginPath, []byte(pluginJSON), 0644); err != nil {
		t.Fatalf("Failed to write plugin file: %v", err)
	}

	detectors, err := LoadDetectorPlugins()
	if err != nil {
		t.Fatalf("LoadDetectorPlugins() returned error: %v", err)
	}

	if len(detectors) != 0 {
		t.Errorf("Expected 0 detectors (disabled), got %d", len(detectors))
	}
}

// TestLoadDetectorPlugins_SkipsInvalidJSON tests that invalid JSON is skipped with no error
func TestLoadDetectorPlugins_SkipsInvalidJSON(t *testing.T) {
	origDir, _ := os.Getwd()
	tmpDir := t.TempDir()
	os.Chdir(tmpDir)
	defer os.Chdir(origDir)

	pluginsDir := filepath.Join(".boil", "plugins", "detectors")
	if err := os.MkdirAll(pluginsDir, 0755); err != nil {
		t.Fatalf("Failed to create plugins dir: %v", err)
	}

	// Write invalid JSON
	if err := os.WriteFile(filepath.Join(pluginsDir, "invalid.json"), []byte("{invalid}"), 0644); err != nil {
		t.Fatalf("Failed to write plugin file: %v", err)
	}

	// Should not error, just skip the invalid file
	detectors, err := LoadDetectorPlugins()
	if err != nil {
		t.Fatalf("LoadDetectorPlugins() returned error: %v", err)
	}

	if len(detectors) != 0 {
		t.Errorf("Expected 0 detectors (invalid skipped), got %d", len(detectors))
	}
}

// TestLoadDetectorPlugins_SkipsNonJSON tests that non-JSON files are skipped
func TestLoadDetectorPlugins_SkipsNonJSON(t *testing.T) {
	origDir, _ := os.Getwd()
	tmpDir := t.TempDir()
	os.Chdir(tmpDir)
	defer os.Chdir(origDir)

	pluginsDir := filepath.Join(".boil", "plugins", "detectors")
	if err := os.MkdirAll(pluginsDir, 0755); err != nil {
		t.Fatalf("Failed to create plugins dir: %v", err)
	}

	// Write a non-JSON file
	if err := os.WriteFile(filepath.Join(pluginsDir, "readme.txt"), []byte("hello"), 0644); err != nil {
		t.Fatalf("Failed to write file: %v", err)
	}

	detectors, err := LoadDetectorPlugins()
	if err != nil {
		t.Fatalf("LoadDetectorPlugins() returned error: %v", err)
	}

	if len(detectors) != 0 {
		t.Errorf("Expected 0 detectors (non-JSON skipped), got %d", len(detectors))
	}
}

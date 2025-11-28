#!/usr/bin/env python3
"""
Test that JSON debug files are created properly.
"""

import json
import os
import sys

from pipeline import run_pipeline, GitState
from pipeline.handlers import register_all_handlers


def test_json_output():
    """Test that pipeline result can be serialized to JSON"""
    print("Testing JSON debug output...")

    # Register handlers
    register_all_handlers()

    # Simulate a permission denied error
    stderr = """
PermissionError: [Errno 13] Permission denied: './test.py'
"""

    git_state = GitState(
        ref="HEAD",
        deleted_files=set(),
        git_toplevel="/root/boiler"
    )

    # Run pipeline
    result = run_pipeline(stderr, "", git_state, debug=False)

    # Convert to dict
    result_dict = result.to_dict()

    # Save to JSON
    json_path = ".boil/test_debug.json"
    os.makedirs(".boil", exist_ok=True)

    with open(json_path, "w") as f:
        json.dump(result_dict, f, indent=2)

    print(f"✓ JSON saved to {json_path}")

    # Verify JSON is valid by reading it back
    with open(json_path, "r") as f:
        loaded = json.load(f)

    print(f"✓ JSON is valid and readable")

    # Print sample
    print("\nSample JSON output:")
    print(json.dumps(result_dict, indent=2))

    # Verify expected fields
    assert "success" in loaded
    assert "clues_detected" in loaded
    assert "plans_generated" in loaded
    assert "plans_attempted" in loaded
    assert "files_modified" in loaded

    print("\n✓ All expected fields present in JSON")

    # Verify clues
    assert len(loaded["clues_detected"]) > 0
    print(f"✓ Detected {len(loaded['clues_detected'])} clue(s)")

    # Verify plans
    assert len(loaded["plans_generated"]) > 0
    print(f"✓ Generated {len(loaded['plans_generated'])} plan(s)")

    print("\n✓✓✓ All tests passed! ✓✓✓")
    return True


if __name__ == "__main__":
    try:
        test_json_output()
        sys.exit(0)
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

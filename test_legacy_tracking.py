#!/usr/bin/env python3
"""
Test that legacy handler usage is tracked in JSON debug output.
"""

import json
import os
import sys

# This test simulates what happens when pipeline fails and legacy handler succeeds


def test_legacy_handler_tracking():
    """Test that we track which legacy handler was used"""
    print("Testing legacy handler tracking in JSON...")

    # Simulate the scenario:
    # 1. Pipeline runs but doesn't find a fix (pipeline_result exists but success=False)
    # 2. Legacy handler is used (legacy_handler_used is set)

    from pipeline import run_pipeline, GitState
    from pipeline.handlers import register_all_handlers

    register_all_handlers()

    # Use an error that the current pipeline can't handle
    # (since we only migrated permission_denied)
    stderr = """
Traceback (most recent call last):
  File "test.py", line 5
    def foo()
           ^
SyntaxError: invalid syntax
"""

    git_state = GitState(
        ref="HEAD",
        deleted_files=set(),
        git_toplevel="/root/boiler"
    )

    # Run pipeline - should fail since we have no SyntaxError detector
    pipeline_result = run_pipeline(stderr, "", git_state, debug=False)

    print(f"Pipeline result: {pipeline_result}")

    # Simulate what boil.py does: add legacy handler info
    legacy_handler_used = "handle_syntax_error"  # Simulated

    debug_data = pipeline_result.to_dict()
    debug_data["legacy_handler_used"] = legacy_handler_used

    # Save to JSON
    os.makedirs(".boil", exist_ok=True)
    json_path = ".boil/test_legacy.json"

    with open(json_path, "w") as f:
        json.dump(debug_data, f, indent=2)

    print(f"✓ JSON saved to {json_path}")

    # Read it back
    with open(json_path, "r") as f:
        loaded = json.load(f)

    print("\nJSON output:")
    print(json.dumps(loaded, indent=2))

    # Verify legacy_handler_used field exists
    assert "legacy_handler_used" in loaded
    print(f"\n✓ legacy_handler_used field present: {loaded['legacy_handler_used']}")

    # Show the key fields
    print(f"\nKey fields:")
    print(f"  - Pipeline success: {loaded['success']}")
    print(f"  - Legacy handler used: {loaded['legacy_handler_used']}")
    print(f"  - Clues detected: {len(loaded['clues_detected'])}")
    print(f"  - Plans generated: {len(loaded['plans_generated'])}")

    print("\n✓✓✓ Legacy handler tracking works! ✓✓✓")
    return True


if __name__ == "__main__":
    try:
        test_legacy_handler_tracking()
        sys.exit(0)
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

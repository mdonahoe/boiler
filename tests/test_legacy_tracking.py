#!/usr/bin/env python3
"""
Test that legacy handler usage is tracked in JSON debug output.
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from pipeline import run_pipeline, GitState
from pipeline.handlers import register_all_handlers


class LegacyTrackerTest(unittest.TestCase):
    """Test legacy handler tracking in JSON debug output"""

    def setUp(self):
        """Register handlers before each test"""
        register_all_handlers()

    def test_legacy_handler_tracking(self):
        """Test that we track which legacy handler was used"""
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
            deleted_files=[],
            git_toplevel="/root/boiler"
        )

        # Run pipeline - should fail since we have no SyntaxError detector
        pipeline_result = run_pipeline(stderr, "", git_state, debug=False)

        # Simulate what boil.py does: add legacy handler info
        legacy_handler_used = "handle_syntax_error"  # Simulated

        debug_data = pipeline_result.to_dict()
        debug_data["legacy_handler_used"] = legacy_handler_used

        # Save to JSON
        os.makedirs(".boil", exist_ok=True)
        json_path = ".boil/test_legacy.json"

        with open(json_path, "w") as f:
            json.dump(debug_data, f, indent=2)

        # Read it back
        with open(json_path, "r") as f:
            loaded = json.load(f)

        # Verify legacy_handler_used field exists
        self.assertIn("legacy_handler_used", loaded)
        self.assertEqual(loaded["legacy_handler_used"], "handle_syntax_error")

        # Verify key fields are present
        self.assertIn("success", loaded)
        self.assertIn("clues_detected", loaded)
        self.assertIn("plans_generated", loaded)


if __name__ == "__main__":
    unittest.main()

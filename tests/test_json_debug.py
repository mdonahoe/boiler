#!/usr/bin/env python3
"""
Test that JSON debug files are created properly.
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from pipeline import run_pipeline, GitState
from pipeline.handlers import register_all_handlers


class JSONDebugTest(unittest.TestCase):
    """Test JSON debug output functionality"""

    def setUp(self):
        """Register handlers before each test"""
        register_all_handlers()

    def test_json_output(self):
        """Test that pipeline result can be serialized to JSON"""
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

        # Verify JSON is valid by reading it back
        with open(json_path, "r") as f:
            loaded = json.load(f)

        # Verify expected fields
        self.assertIn("success", loaded)
        self.assertIn("clues_detected", loaded)
        self.assertIn("plans_generated", loaded)
        self.assertIn("plans_attempted", loaded)
        self.assertIn("files_modified", loaded)

        # Verify clues
        self.assertGreater(len(loaded["clues_detected"]), 0)

        # Verify plans
        self.assertGreater(len(loaded["plans_generated"]), 0)


if __name__ == "__main__":
    unittest.main()

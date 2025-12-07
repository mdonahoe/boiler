#!/usr/bin/env python3
"""
Simple test to verify the pipeline system works.
"""

import sys
import os
import unittest

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from pipeline import run_pipeline, GitState
from pipeline.handlers import register_all_handlers


class PipelineSystemTest(unittest.TestCase):
    """Test pipeline system functionality"""

    def setUp(self):
        """Register handlers before each test"""
        register_all_handlers()

    def test_permission_denied_detection(self):
        """Test that permission denied errors are detected and planned"""
        # Simulate a permission denied error
        stderr = """
PermissionError: [Errno 13] Permission denied: './test.py'
"""

        git_state = GitState(
            ref="HEAD",
            deleted_files=[],
            git_toplevel="/root/boiler"
        )

        result = run_pipeline(stderr, "", git_state, debug=False)

        # Should generate plans and detect clues even if execution fails
        self.assertIsNotNone(result.clues_detected, "Should detect clues")
        self.assertGreater(len(result.clues_detected), 0, "Should have clues detected")
        self.assertIsNotNone(result.plans_generated, "Should generate plans")
        self.assertGreater(len(result.plans_generated), 0, "Should have plans generated")

    def test_no_error(self):
        """Test that pipeline returns gracefully when no errors detected"""
        # No error messages
        stderr = "Everything is fine!"
        stdout = "Tests passed!"

        git_state = GitState(
            ref="HEAD",
            deleted_files=[],
            git_toplevel="/root/boiler"
        )

        result = run_pipeline(stderr, stdout, git_state, debug=False)

        self.assertFalse(result.success, "Pipeline should report no success when no errors to fix")
        self.assertIn("No error clues detected", result.error_message or "")

    def test_missing_file_in_git(self):
        """Test validation catches files that don't exist in git"""
        # Permission error for a file that definitely doesn't exist in git
        stderr = """
PermissionError: [Errno 13] Permission denied: './nonexistent_file_xyz123.py'
"""

        git_state = GitState(
            ref="HEAD",
            deleted_files=[],
            git_toplevel="/root/boiler"
        )

        result = run_pipeline(stderr, "", git_state, debug=False)

        # Should fail because file doesn't exist in git
        self.assertFalse(result.success, "Pipeline should reject nonexistent file")


if __name__ == "__main__":
    unittest.main()

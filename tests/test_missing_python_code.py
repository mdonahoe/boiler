#!/usr/bin/env python3
"""
Test that the missing Python code detector and executor work correctly.
"""

import sys
import os
import unittest
import tempfile
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from pipeline import run_pipeline, GitState
from pipeline.handlers import register_all_handlers


class MissingPythonCodeTest(unittest.TestCase):
    """Test missing Python code detection and restoration"""

    def setUp(self):
        """Register handlers before each test"""
        register_all_handlers()

    def test_missing_class_detection(self):
        """Test that missing class definitions are detected"""
        stderr = "AssertionError: 'class TestClass' not found in '...example.py - 5 lines...'"

        git_state = GitState(
            ref="HEAD",
            deleted_files=set(),
            git_toplevel="/root/boiler"
        )

        result = run_pipeline(stderr, "", git_state, debug=False)

        # Should detect the missing class
        self.assertIsNotNone(result.clues_detected, "Should detect clues")
        self.assertGreater(len(result.clues_detected), 0, "Should have at least one clue")
        self.assertEqual(result.clues_detected[0].clue_type, "missing_python_code")
        self.assertEqual(result.clues_detected[0].context.get("element_name"), "TestClass")

    def test_missing_function_detection(self):
        """Test that missing function definitions are detected"""
        stderr = "AssertionError: 'def hello_world' not found in '...test.py - 10 lines...'"

        git_state = GitState(
            ref="HEAD",
            deleted_files=set(),
            git_toplevel="/root/boiler"
        )

        result = run_pipeline(stderr, "", git_state, debug=False)

        # Should detect the missing function
        self.assertIsNotNone(result.clues_detected)
        self.assertGreater(len(result.clues_detected), 0)
        self.assertEqual(result.clues_detected[0].clue_type, "missing_python_code")
        self.assertEqual(result.clues_detected[0].context.get("element_name"), "hello_world")

    def test_missing_python_code_skips_nonexistent_files(self):
        """Test that planner skips files that don't exist"""
        stderr = "AssertionError: 'class Foo' not found in '...nonexistent.py - 3 lines...'"

        git_state = GitState(
            ref="HEAD",
            deleted_files=set(),
            git_toplevel="/root/boiler"
        )

        result = run_pipeline(stderr, "", git_state, debug=False)

        # Should detect the clue but not plan a repair (file doesn't exist)
        self.assertIsNotNone(result.clues_detected)
        self.assertGreater(len(result.clues_detected), 0)
        # Plans should be empty (file doesn't exist)
        self.assertEqual(len(result.plans_generated or []), 0)

    def test_missing_class_with_escaped_newlines(self):
        """Test detection when filename is preceded by escaped newlines (\\n)"""
        # This mimics the actual error from the dim test suite
        stderr = r"AssertionError: 'class TestClass' not found in '#!/usr/bin/env python3\n\"\"\"\nTest Python file\n\"\"\"\n\ndef hello_world():\n    print(\"Hello\")\n~\n~\nexample.py - 12 lines                                              python | 1/12\nhl_counts = 179, lines = 12' : Expected to see class definition"

        git_state = GitState(
            ref="HEAD",
            deleted_files=set(),
            git_toplevel="/root/boiler"
        )

        result = run_pipeline(stderr, "", git_state, debug=False)

        # Should detect the missing class with correct filename (not "nexample.py")
        self.assertIsNotNone(result.clues_detected, "Should detect clues")
        self.assertGreater(len(result.clues_detected), 0, "Should have at least one clue")
        self.assertEqual(result.clues_detected[0].clue_type, "missing_python_code")
        self.assertEqual(result.clues_detected[0].context.get("element_name"), "TestClass")
        self.assertEqual(result.clues_detected[0].context.get("file_path"), "example.py",
                        "Should extract correct filename, not 'nexample.py'")


if __name__ == "__main__":
    unittest.main()

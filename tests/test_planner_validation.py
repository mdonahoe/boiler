#!/usr/bin/env python3
"""
Test that planners don't create plans for files that are already restored.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from pipeline import run_pipeline, GitState
from pipeline.handlers import register_all_handlers


class PlannerValidationTest(unittest.TestCase):
    """Test planner validation behavior"""

    def setUp(self):
        """Register handlers before each test"""
        register_all_handlers()

    def test_planner_skips_existing_file(self):
        """Test that planner doesn't create plan for file that already matches git"""
        # Simulate error for test.py which already exists and matches git
        stderr = """
/tmp/ex_bar.c:82:10: fatal error: test.py: No such file or directory
   82 | #include "test.py"
       |          ^~~~~~~~~~
compilation terminated.
"""

        # test.py exists in the boiler repo and matches HEAD
        git_state = GitState(
            ref="HEAD",
            deleted_files=set(),
            git_toplevel="/root/boiler"
        )

        # Change to boiler directory where test.py exists
        original_dir = os.getcwd()
        os.chdir("/root/boiler")

        try:
            result = run_pipeline(stderr, "", git_state, debug=False)

            # Check that clues were detected
            self.assertIsNotNone(result.clues_detected, "Should have detected error")
            self.assertGreater(len(result.clues_detected), 0, "Should have at least one clue")

            # Check that NO plans were generated (file already matches git)
            self.assertEqual(
                len(result.plans_generated or []), 0,
                "Should not have generated plans for existing file"
            )

            # Should report failure since no plans could be generated
            self.assertFalse(result.success, "Should report failure when no plans available")

        finally:
            os.chdir(original_dir)

    def test_planner_creates_plan_for_missing_file(self):
        """Test that planner DOES create plan when file is actually missing"""
        stderr = "cat: nonexistent123.txt: No such file or directory"

        git_state = GitState(
            ref="HEAD",
            deleted_files={"nonexistent123.txt"},
            git_toplevel="/root/boiler"
        )

        result = run_pipeline(stderr, "", git_state, debug=False)

        # Check that clues were detected
        self.assertIsNotNone(result.clues_detected, "Should have detected error")
        self.assertGreater(len(result.clues_detected), 0, "Should have at least one clue")

        # Check that plans WERE generated (file doesn't exist)
        self.assertIsNotNone(result.plans_generated, "Should generate plans")
        self.assertGreater(len(result.plans_generated), 0, "Should have plans generated for missing file")


if __name__ == "__main__":
    unittest.main()

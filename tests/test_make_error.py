#!/usr/bin/env python3
"""
Test that make missing target errors are detected and planned.
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from pipeline import run_pipeline, GitState
from pipeline.handlers import register_all_handlers


class MakeErrorTest(unittest.TestCase):
    """Test make error detection and planning"""

    def setUp(self):
        """Register handlers before each test"""
        register_all_handlers()

    def test_make_missing_target(self):
        """Test detection of make missing target error"""
        # Use the actual error from /root/dim/.boil/iter1.exit2.txt
        stderr = """make: *** No rule to make target 'dim.c', needed by 'dim'.  Stop.
"""

        git_state = GitState(
            ref="HEAD",
            deleted_files={"dim.c"},  # Simulate that dim.c is deleted
            git_toplevel="/root/dim"
        )

        result = run_pipeline(stderr, "", git_state, debug=False)

        # Verify detection worked
        self.assertIsNotNone(result.clues_detected, "Should detect clues")
        self.assertGreater(len(result.clues_detected), 0, "Should have clues detected")
        self.assertEqual(result.clues_detected[0].clue_type, "make_missing_target")

        # Verify plans were generated
        self.assertIsNotNone(result.plans_generated, "Should generate plans")
        self.assertGreater(len(result.plans_generated), 0, "Should have plans generated")

        # Check that we have a plan to restore dim.c
        has_dim_c_plan = any(
            "dim.c" in plan.target_file
            for plan in result.plans_generated
        )
        self.assertTrue(has_dim_c_plan, "Should have plan to restore dim.c")


if __name__ == "__main__":
    unittest.main()

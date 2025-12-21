#!/usr/bin/env python3
"""
Test that planners don't create plans for files that are already restored.
"""

import os
import sys
import unittest
import shutil
import tempfile
import subprocess

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from pipeline import run_pipeline, GitState
from pipeline.handlers import register_all_handlers


class PlannerValidationTest(unittest.TestCase):
    """Test planner validation behavior"""

    @classmethod
    def setUpClass(cls):
        """Copy simple repo to /tmp for all tests"""
        simple_before_src = os.path.join(os.path.dirname(os.path.dirname(__file__)), "example_repos", "simple", "before")
        cls.temp_dir = tempfile.mkdtemp(prefix="boil_test_")
        cls.simple_repo_tmp = os.path.join(cls.temp_dir, "simple")
        shutil.copytree(simple_before_src, cls.simple_repo_tmp)
        
        # Initialize as a git repo
        subprocess.run(["git", "init"], cwd=cls.simple_repo_tmp, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=cls.simple_repo_tmp, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=cls.simple_repo_tmp, capture_output=True)
        subprocess.run(["git", "add", "."], cwd=cls.simple_repo_tmp, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=cls.simple_repo_tmp, capture_output=True)

    @classmethod
    def tearDownClass(cls):
        """Clean up temp directory"""
        if hasattr(cls, 'temp_dir') and os.path.exists(cls.temp_dir):
            shutil.rmtree(cls.temp_dir)

    def setUp(self):
        """Register handlers before each test"""
        register_all_handlers()

    def test_planner_skips_existing_file(self):
        """Test that planner doesn't create plan for file that already matches git"""
        # Simulate error for a file that exists in the temp repo
        stderr = """
    /tmp/ex_bar.c:82:10: fatal error: simple.c: No such file or directory
    82 | #include "simple.c"
        |          ^~~~~~~~~
    compilation terminated.
    """

        # simple.c exists in the simple repo and matches HEAD
        git_state = GitState(
            ref="HEAD",
            deleted_files=[],
            git_toplevel=self.simple_repo_tmp
        )

        # Change to temp repo directory
        original_dir = os.getcwd()
        os.chdir(self.simple_repo_tmp)

        try:
            result = run_pipeline(stderr, "", git_state, debug=False, execute=False)

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
            deleted_files=["nonexistent123.txt"],
            git_toplevel=self.simple_repo_tmp
        )

        # Change to temp repo directory
        original_dir = os.getcwd()
        os.chdir(self.simple_repo_tmp)

        try:
            result = run_pipeline(stderr, "", git_state, debug=False, execute=False)

            # Check that clues were detected
            self.assertIsNotNone(result.clues_detected, "Should have detected error")
            self.assertGreater(len(result.clues_detected), 0, "Should have at least one clue")

            # Check that plans WERE generated (file doesn't exist)
            self.assertIsNotNone(result.plans_generated, "Should generate plans")
            self.assertGreater(len(result.plans_generated), 0, "Should have plans generated for missing file")

        finally:
            os.chdir(original_dir)


if __name__ == "__main__":
    unittest.main()

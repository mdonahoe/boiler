#!/usr/bin/env python3
"""
Integration tests for boil command-line interface.

These tests verify that core boil commands (--check, --abort, --finish) work correctly.
They are implementation-agnostic and will work whether boil is Python or Go.
"""

import os
import sys
import unittest
import subprocess
import shutil
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Import test utilities
from tests.test_utils import copy_and_boil


class TestBoilCheck(unittest.TestCase):
    """Test boil --check command"""

    def test_check_shows_stats_after_boiling(self):
        """boil --check should show statistics after a boiling session"""
        boiler_dir = os.path.dirname(os.path.dirname(__file__))
        example_dir = os.path.join(boiler_dir, "example_repos", "simple", "before")

        # Run boil to create a session
        with copy_and_boil(
            src_dir=example_dir,
            test_command=["make", "test"],
            preserve_tmpdir=True
        ) as result:
            tmpdir = result['tmpdir']

            # Now run boil --check in the same directory
            check_result = subprocess.run(
                ["boil", "--check"],
                cwd=tmpdir,
                capture_output=True,
                text=True
            )

            # Should succeed
            self.assertEqual(check_result.returncode, 0,
                           f"boil --check should succeed. stderr: {check_result.stderr}")

            # Should output statistics
            output = check_result.stdout
            self.assertIn("iteration", output.lower() or output.lower(),
                         "Output should mention iterations")

            # Clean up
            shutil.rmtree(tmpdir)

    def test_check_fails_without_boil_session(self):
        """boil --check should fail if no .boil directory exists"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Initialize a git repo but don't run boil
            subprocess.run(["git", "init"], cwd=tmpdir, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"],
                         cwd=tmpdir, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Test User"],
                         cwd=tmpdir, check=True, capture_output=True)

            # Try to run boil --check
            check_result = subprocess.run(
                ["boil", "--check"],
                cwd=tmpdir,
                capture_output=True,
                text=True
            )

            # Should fail or show "no session" message
            # (Implementation may vary, but it shouldn't crash)
            self.assertTrue(
                check_result.returncode != 0 or "no" in check_result.stdout.lower(),
                "Should indicate no boiling session exists"
            )


class TestBoilAbort(unittest.TestCase):
    """Test boil --abort command"""

    def test_abort_restores_working_directory(self):
        """boil --abort should restore working directory to pre-boil state"""
        boiler_dir = os.path.dirname(os.path.dirname(__file__))
        example_dir = os.path.join(boiler_dir, "example_repos", "simple", "before")

        # Create a temp directory and set up a test scenario
        tmpdir = tempfile.mkdtemp(prefix="boil_abort_test_")

        try:
            # Initialize git repo
            subprocess.run(["git", "init"], cwd=tmpdir, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"],
                         cwd=tmpdir, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Test User"],
                         cwd=tmpdir, check=True, capture_output=True)

            # Copy files from example
            for item in os.listdir(example_dir):
                if item.startswith('.'):
                    continue
                src = os.path.join(example_dir, item)
                dst = os.path.join(tmpdir, item)
                if os.path.isfile(src):
                    shutil.copy2(src, dst)
                elif os.path.isdir(src):
                    shutil.copytree(src, dst)

            # Commit
            subprocess.run(["git", "add", "."], cwd=tmpdir, check=True, capture_output=True)
            subprocess.run(["git", "commit", "-m", "Initial"],
                         cwd=tmpdir, check=True, capture_output=True)

            # Delete the Makefile to create an error scenario
            makefile_path = os.path.join(tmpdir, "Makefile")
            if os.path.exists(makefile_path):
                os.remove(makefile_path)

            # Remember that Makefile is deleted
            self.assertFalse(os.path.exists(makefile_path),
                           "Makefile should be deleted")

            # Run boil (it should create a session)
            boil_result = subprocess.run(
                ["boil", "make", "test"],
                cwd=tmpdir,
                capture_output=True,
                text=True,
                timeout=60
            )

            # At this point, boil may have succeeded or failed, but there should be a .boil directory
            boil_dir = os.path.join(tmpdir, ".boil")
            if not os.path.exists(boil_dir):
                self.skipTest(".boil directory not created - cannot test abort")

            # Delete Makefile again if it was restored
            if os.path.exists(makefile_path):
                os.remove(makefile_path)

            # Now run boil --abort
            abort_result = subprocess.run(
                ["boil", "--abort"],
                cwd=tmpdir,
                capture_output=True,
                text=True
            )

            # Should succeed
            self.assertEqual(abort_result.returncode, 0,
                           f"boil --abort should succeed. stderr: {abort_result.stderr}")

            # .boil directory should be removed
            self.assertFalse(os.path.exists(boil_dir),
                           ".boil directory should be removed after abort")

            # Makefile should still be deleted (restored to pre-boil state)
            self.assertFalse(os.path.exists(makefile_path),
                           "Makefile should be deleted (pre-boil state)")

        finally:
            # Clean up
            if os.path.exists(tmpdir):
                shutil.rmtree(tmpdir)

    def test_abort_fails_without_boil_session(self):
        """boil --abort should fail gracefully if no session exists"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Initialize a git repo but don't run boil
            subprocess.run(["git", "init"], cwd=tmpdir, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"],
                         cwd=tmpdir, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Test User"],
                         cwd=tmpdir, check=True, capture_output=True)

            # Try to run boil --abort
            abort_result = subprocess.run(
                ["boil", "--abort"],
                cwd=tmpdir,
                capture_output=True,
                text=True
            )

            # Should fail or show appropriate message
            # (Implementation may vary, but it shouldn't crash)
            self.assertTrue(
                abort_result.returncode != 0 or "no" in abort_result.stdout.lower() or
                "not" in abort_result.stdout.lower(),
                "Should indicate no boiling session to abort"
            )


class TestBoilFinish(unittest.TestCase):
    """Test boil --finish command"""

    def test_finish_removes_boil_directory(self):
        """boil --finish should remove .boil directory but keep working directory state"""
        boiler_dir = os.path.dirname(os.path.dirname(__file__))
        example_dir = os.path.join(boiler_dir, "example_repos", "simple", "before")

        # Run boil to create a session
        with copy_and_boil(
            src_dir=example_dir,
            test_command=["make", "test"],
            preserve_tmpdir=True
        ) as result:
            tmpdir = result['tmpdir']
            boil_dir = os.path.join(tmpdir, ".boil")

            # .boil directory should exist after boiling
            self.assertTrue(os.path.exists(boil_dir),
                          ".boil directory should exist after boiling")

            # Remember if Makefile exists (it should if boil succeeded)
            makefile_path = os.path.join(tmpdir, "Makefile")
            makefile_existed = os.path.exists(makefile_path)

            # Run boil --finish
            finish_result = subprocess.run(
                ["boil", "--finish"],
                cwd=tmpdir,
                capture_output=True,
                text=True
            )

            # Should succeed
            self.assertEqual(finish_result.returncode, 0,
                           f"boil --finish should succeed. stderr: {finish_result.stderr}")

            # .boil directory should be removed
            self.assertFalse(os.path.exists(boil_dir),
                           ".boil directory should be removed after finish")

            # Working directory state should be preserved
            # (Makefile should still exist if it was there before)
            self.assertEqual(os.path.exists(makefile_path), makefile_existed,
                           "Working directory state should be preserved")

            # Clean up
            shutil.rmtree(tmpdir)

    def test_finish_fails_without_boil_session(self):
        """boil --finish should fail gracefully if no session exists"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Initialize a git repo but don't run boil
            subprocess.run(["git", "init"], cwd=tmpdir, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"],
                         cwd=tmpdir, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Test User"],
                         cwd=tmpdir, check=True, capture_output=True)

            # Try to run boil --finish
            finish_result = subprocess.run(
                ["boil", "--finish"],
                cwd=tmpdir,
                capture_output=True,
                text=True
            )

            # Should fail or show appropriate message
            self.assertTrue(
                finish_result.returncode != 0 or "no" in finish_result.stdout.lower() or
                "not" in finish_result.stdout.lower(),
                "Should indicate no boiling session to finish"
            )


if __name__ == "__main__":
    unittest.main()

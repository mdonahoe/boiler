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

# Use local boil binary, not system-installed one
BOILER_DIR = os.path.dirname(os.path.dirname(__file__))
BOIL_SCRIPT = os.path.join(BOILER_DIR, "boil")


class TestBoilCheck(unittest.TestCase):
    """Test boil --check command"""

    def test_check_shows_stats_after_boiling(self):
        """boil --check should show statistics after a boiling session"""
        example_dir = os.path.join(BOILER_DIR, "example_repos", "simple", "before")

        # Run boil to create a session
        with copy_and_boil(
            src_dir=example_dir,
            test_command=["make", "test"],
            preserve_tmpdir=True
        ) as result:
            tmpdir = result['tmpdir']

            # Now run boil --check in the same directory (use local binary)
            check_result = subprocess.run(
                [BOIL_SCRIPT, "--check"],
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
                [BOIL_SCRIPT, "--check"],
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
        example_dir = os.path.join(BOILER_DIR, "example_repos", "simple", "before")

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
                [BOIL_SCRIPT, "make", "test"],
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
                [BOIL_SCRIPT, "--abort"],
                cwd=tmpdir,
                capture_output=True,
                text=True
            )

            # Should succeed
            self.assertEqual(abort_result.returncode, 0,
                           f"boil --abort should succeed. stderr: {abort_result.stderr}")

            # .boil/iterations directory should be removed (but .boil may remain for plugins)
            iterations_dir = os.path.join(tmpdir, ".boil", "iterations")
            self.assertFalse(os.path.exists(iterations_dir),
                           ".boil/iterations should be removed after abort")

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
                [BOIL_SCRIPT, "--abort"],
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
        example_dir = os.path.join(BOILER_DIR, "example_repos", "simple", "before")

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
                [BOIL_SCRIPT, "--finish"],
                cwd=tmpdir,
                capture_output=True,
                text=True
            )

            # Should succeed
            self.assertEqual(finish_result.returncode, 0,
                           f"boil --finish should succeed. stderr: {finish_result.stderr}")

            # .boil/iterations directory should be removed (but .boil may remain for plugins)
            iterations_dir = os.path.join(tmpdir, ".boil", "iterations")
            self.assertFalse(os.path.exists(iterations_dir),
                           ".boil/iterations should be removed after finish")

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
                [BOIL_SCRIPT, "--finish"],
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


class TestBoilUncommittedChanges(unittest.TestCase):
    """Test that boil refuses to run when there are uncommitted changes"""

    def test_boil_refuses_with_untracked_files(self):
        """boil should refuse to run when there are untracked files"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Initialize a git repo
            subprocess.run(["git", "init"], cwd=tmpdir, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"],
                         cwd=tmpdir, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Test User"],
                         cwd=tmpdir, check=True, capture_output=True)

            # Create and commit a file
            with open(os.path.join(tmpdir, "committed.txt"), "w") as f:
                f.write("committed content")
            subprocess.run(["git", "add", "committed.txt"], cwd=tmpdir, check=True, capture_output=True)
            subprocess.run(["git", "commit", "-m", "Initial commit"],
                         cwd=tmpdir, check=True, capture_output=True)

            # Create an untracked file (not in git)
            with open(os.path.join(tmpdir, "new_file.txt"), "w") as f:
                f.write("new content that would be lost")

            # Try to run boil - it should fail
            result = subprocess.run(
                [BOIL_SCRIPT, "echo", "test"],
                cwd=tmpdir,
                capture_output=True,
                text=True
            )

            # Should fail
            self.assertNotEqual(result.returncode, 0,
                              "boil should fail when there are untracked files")

            # Should mention uncommitted additions in the error message
            combined_output = result.stdout + result.stderr
            self.assertIn("uncommitted additions", combined_output.lower(),
                         f"Error should mention uncommitted additions. Output: {combined_output}")

    def test_boil_refuses_with_modified_files(self):
        """boil should refuse to run when there are modified but uncommitted files"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Initialize a git repo
            subprocess.run(["git", "init"], cwd=tmpdir, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"],
                         cwd=tmpdir, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Test User"],
                         cwd=tmpdir, check=True, capture_output=True)

            # Create and commit a file
            with open(os.path.join(tmpdir, "myfile.txt"), "w") as f:
                f.write("original content")
            subprocess.run(["git", "add", "myfile.txt"], cwd=tmpdir, check=True, capture_output=True)
            subprocess.run(["git", "commit", "-m", "Initial commit"],
                         cwd=tmpdir, check=True, capture_output=True)

            # Modify the file (add a new line)
            with open(os.path.join(tmpdir, "myfile.txt"), "a") as f:
                f.write("\nnew line that would be lost")

            # Try to run boil - it should fail
            result = subprocess.run(
                [BOIL_SCRIPT, "echo", "test"],
                cwd=tmpdir,
                capture_output=True,
                text=True
            )

            # Should fail
            self.assertNotEqual(result.returncode, 0,
                              "boil should fail when there are modified files")

            # Should mention uncommitted additions and the file
            combined_output = result.stdout + result.stderr
            self.assertIn("uncommitted additions", combined_output.lower(),
                         f"Error should mention uncommitted additions. Output: {combined_output}")
            self.assertIn("myfile.txt", combined_output,
                         f"Error should mention the modified file. Output: {combined_output}")

    def test_boil_refuses_with_staged_changes(self):
        """boil should refuse to run when there are staged but uncommitted changes"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Initialize a git repo
            subprocess.run(["git", "init"], cwd=tmpdir, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"],
                         cwd=tmpdir, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Test User"],
                         cwd=tmpdir, check=True, capture_output=True)

            # Create and commit a file
            with open(os.path.join(tmpdir, "committed.txt"), "w") as f:
                f.write("committed content")
            subprocess.run(["git", "add", "committed.txt"], cwd=tmpdir, check=True, capture_output=True)
            subprocess.run(["git", "commit", "-m", "Initial commit"],
                         cwd=tmpdir, check=True, capture_output=True)

            # Create a new file and stage it (but don't commit)
            with open(os.path.join(tmpdir, "staged_new.txt"), "w") as f:
                f.write("new staged content that would be lost")
            subprocess.run(["git", "add", "staged_new.txt"], cwd=tmpdir, check=True, capture_output=True)

            # Try to run boil - it should fail
            result = subprocess.run(
                [BOIL_SCRIPT, "echo", "test"],
                cwd=tmpdir,
                capture_output=True,
                text=True
            )

            # Should fail
            self.assertNotEqual(result.returncode, 0,
                              "boil should fail when there are staged new files")

            # Should mention uncommitted additions in the error message
            combined_output = result.stdout + result.stderr
            self.assertIn("uncommitted additions", combined_output.lower(),
                         f"Error should mention uncommitted additions. Output: {combined_output}")

    def test_boil_allows_file_deletions(self):
        """boil should allow running when entire files are deleted (tracked in git)"""
        example_dir = os.path.join(BOILER_DIR, "example_repos", "simple", "before")

        with tempfile.TemporaryDirectory() as tmpdir:
            # Initialize a git repo
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
            subprocess.run(["git", "commit", "-m", "Initial commit"],
                         cwd=tmpdir, check=True, capture_output=True)

            # Delete a file (this is a deletion, not an addition - should be allowed)
            makefile_path = os.path.join(tmpdir, "Makefile")
            if os.path.exists(makefile_path):
                os.remove(makefile_path)

            # Try to run boil - it should NOT fail due to uncommitted changes
            # (deletions are OK because they're tracked in git)
            result = subprocess.run(
                [BOIL_SCRIPT, "make", "test"],
                cwd=tmpdir,
                capture_output=True,
                text=True,
                timeout=60
            )

            # Should not fail due to uncommitted additions
            combined_output = result.stdout + result.stderr
            self.assertNotIn("uncommitted additions", combined_output.lower(),
                           f"Should not fail due to uncommitted additions. Output: {combined_output}")

    def test_boil_allows_line_deletions(self):
        """boil should allow running when only lines are removed from a file"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Initialize a git repo
            subprocess.run(["git", "init"], cwd=tmpdir, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"],
                         cwd=tmpdir, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Test User"],
                         cwd=tmpdir, check=True, capture_output=True)

            # Create a file with multiple lines
            with open(os.path.join(tmpdir, "myfile.txt"), "w") as f:
                f.write("line1\nline2\nline3\nline4\n")
            subprocess.run(["git", "add", "myfile.txt"], cwd=tmpdir, check=True, capture_output=True)
            subprocess.run(["git", "commit", "-m", "Initial commit"],
                         cwd=tmpdir, check=True, capture_output=True)

            # Remove some lines (deletion only, no additions)
            with open(os.path.join(tmpdir, "myfile.txt"), "w") as f:
                f.write("line1\nline4\n")

            # Try to run boil - it should NOT fail due to uncommitted changes
            # (removing lines is OK because the content is tracked in git)
            result = subprocess.run(
                [BOIL_SCRIPT, "echo", "test"],
                cwd=tmpdir,
                capture_output=True,
                text=True
            )

            # Should not fail due to uncommitted additions
            combined_output = result.stdout + result.stderr
            self.assertNotIn("uncommitted additions", combined_output.lower(),
                           f"Should not fail due to uncommitted additions when only removing lines. Output: {combined_output}")


class TestBoilSearch(unittest.TestCase):
    """Test boil --search command"""

    def test_search_requires_command(self):
        """boil --search should require a test command"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Initialize a git repo
            subprocess.run(["git", "init"], cwd=tmpdir, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"],
                         cwd=tmpdir, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Test User"],
                         cwd=tmpdir, check=True, capture_output=True)

            # Create and commit a file
            with open(os.path.join(tmpdir, "test.txt"), "w") as f:
                f.write("test content")
            subprocess.run(["git", "add", "."], cwd=tmpdir, check=True, capture_output=True)
            subprocess.run(["git", "commit", "-m", "Initial"],
                         cwd=tmpdir, check=True, capture_output=True)

            # Try to run boil --search without a command
            result = subprocess.run(
                [BOIL_SCRIPT, "--search"],
                cwd=tmpdir,
                capture_output=True,
                text=True
            )

            # Should fail
            self.assertNotEqual(result.returncode, 0,
                              "boil --search should fail without a command")

            # Should mention that a command is required
            combined_output = result.stdout + result.stderr
            self.assertTrue(
                "require" in combined_output.lower() or "command" in combined_output.lower(),
                f"Should indicate a command is required. Output: {combined_output}"
            )

    def test_search_works_on_simple_repo(self):
        """boil --search should work on a simple example repo"""
        example_dir = os.path.join(BOILER_DIR, "example_repos", "simple", "before")

        if not os.path.exists(example_dir):
            self.skipTest(f"Simple example repo not found at {example_dir}")

        # Run boil --search
        with copy_and_boil(
            src_dir=example_dir,
            test_command=["make", "test"],
            boil_args=["--search"],
            preserve_tmpdir=False,
            verify_before=True,
            delete_files=True,
            timeout=180  # Search takes longer (two phases)
        ) as result:
            # Should succeed
            self.assertTrue(
                result['success'],
                f"boil --search should succeed on simple repo.\n"
                f"stdout: {result['boil_result'].stdout[-2000:]}\n"
                f"stderr: {result['boil_result'].stderr[-2000:]}"
            )

            # Output should mention search phases
            combined_output = result['boil_result'].stdout + result['boil_result'].stderr
            self.assertIn("Phase 1", combined_output,
                         "Output should mention Phase 1")
            self.assertIn("Phase 2", combined_output,
                         "Output should mention Phase 2")

    def test_search_on_dim_repo(self):
        """boil --search should work on dim repo and restore dim.c"""
        example_dir = os.path.join(BOILER_DIR, "example_repos", "dim", "before")

        if not os.path.exists(example_dir):
            self.skipTest(f"Dim example repo not found at {example_dir}")

        # Get original dim.c size for comparison
        original_dim_c = os.path.join(example_dir, "dim.c")
        if not os.path.exists(original_dim_c):
            self.skipTest("dim.c not found in dim example repo")

        original_size = os.path.getsize(original_dim_c)

        # Run boil --search
        with copy_and_boil(
            src_dir=example_dir,
            test_command=["make", "test"],
            boil_args=["--search"],
            preserve_tmpdir=True,  # Keep tmpdir to check file sizes
            verify_before=True,
            delete_files=True,
            timeout=300  # Search on dim repo may take longer
        ) as result:
            tmpdir = result['tmpdir']

            try:
                # Should succeed
                self.assertTrue(
                    result['success'],
                    f"boil --search should succeed on dim repo.\n"
                    f"stdout: {result['boil_result'].stdout[-2000:]}\n"
                    f"stderr: {result['boil_result'].stderr[-2000:]}"
                )

                # Check dim.c was restored
                restored_dim_c = os.path.join(tmpdir, "dim.c")
                self.assertTrue(
                    os.path.exists(restored_dim_c),
                    "dim.c should be restored after boil --search"
                )

                restored_size = os.path.getsize(restored_dim_c)

                # Verify test still passes with the restored file
                test_result = subprocess.run(
                    ["make", "test"],
                    cwd=tmpdir,
                    capture_output=True,
                    text=True
                )
                self.assertEqual(
                    test_result.returncode, 0,
                    f"Tests should pass with restored dim.c.\n"
                    f"stdout: {test_result.stdout}\n"
                    f"stderr: {test_result.stderr}"
                )

                # Search mode Phase 2 should minimize dim.c by removing unused functions
                self.assertLess(
                    restored_size, original_size,
                    f"dim.c should be smaller after search mode minimization. "
                    f"Original: {original_size} bytes, Restored: {restored_size} bytes"
                )
                print(f"SUCCESS: dim.c reduced from {original_size} to {restored_size} bytes "
                      f"({original_size - restored_size} bytes smaller)")
            finally:
                # Clean up tmpdir
                import shutil
                shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()

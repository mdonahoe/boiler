#!/usr/bin/env python3
"""
Test boiling example repositories end-to-end.

This test creates a temporary git repository, copies files from the
example_repos/*/before/ directory, commits them, deletes all files,
and verifies that boiling successfully restores enough files to pass "make test"
"""

import sys
import os
import unittest
import tempfile
import shutil
import subprocess

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from pipeline.handlers import register_all_handlers


class ExampleReposTest(unittest.TestCase):
    """Test boiling of example repositories"""

    def setUp(self):
        """Register handlers before each test"""
        register_all_handlers()

    def test_simple_repo_boiling(self):
        """Test that the simple example repo can be boiled successfully"""
        self._test_repo_boiling("simple")

    def test_dim_repo_boiling(self):
        """Test that the dim example repo can be boiled successfully"""
        self._test_repo_boiling("dim")

    def _test_repo_boiling(self, repo_name):
        """Helper function to test boiling of a repo"""
        # Get the path to the boil script and example repo
        boiler_dir = os.path.dirname(os.path.dirname(__file__))
        boil_script = os.path.join(boiler_dir, "boil")
        # Use before/ folder - it contains the files that should be committed to git
        # After deletion, boiling should restore them
        example_before_dir = os.path.join(boiler_dir, "example_repos", repo_name, "before")

        # Verify the example directory exists
        self.assertTrue(os.path.exists(example_before_dir),
                       f"Example directory not found: {example_before_dir}")

        # Create a temporary directory for the test
        with tempfile.TemporaryDirectory() as tmpdir:
            # Initialize git repo
            subprocess.run(["git", "init"], cwd=tmpdir, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"],
                          cwd=tmpdir, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Test User"],
                          cwd=tmpdir, check=True, capture_output=True)

            # Copy files from before/ directory (these will be committed to git)
            for item in os.listdir(example_before_dir):
                # Skip .boil directory and other hidden files/dirs
                if item.startswith('.'):
                    continue
                src = os.path.join(example_before_dir, item)
                dst = os.path.join(tmpdir, item)
                if os.path.isfile(src):
                    shutil.copy2(src, dst)
                elif os.path.isdir(src):
                    shutil.copytree(src, dst)

            # Make scripts executable if needed
            for item in os.listdir(example_before_dir):
                if not item.startswith('.'):
                    item_path = os.path.join(tmpdir, item)
                    if os.path.isfile(item_path) and os.access(os.path.join(example_before_dir, item), os.X_OK):
                        os.chmod(item_path, 0o755)

            # Verify Makefile was copied
            self.assertTrue(os.path.exists(os.path.join(tmpdir, "Makefile")),
                          f"Makefile should be copied for {repo_name}")

            # Commit all files
            subprocess.run(["git", "add", "."], cwd=tmpdir, check=True, capture_output=True)
            subprocess.run(["git", "commit", "-m", "Initial commit"],
                          cwd=tmpdir, check=True, capture_output=True)

            # Verify the test works before deletion
            result = subprocess.run(["make", "test"], cwd=tmpdir, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0,
                           f"Test should pass before deletion for {repo_name}. Output:\n{result.stdout}\n{result.stderr}")

            # Delete all files (but keep .git)
            for item in os.listdir(tmpdir):
                if item == ".git":
                    continue
                item_path = os.path.join(tmpdir, item)
                if os.path.isfile(item_path):
                    os.remove(item_path)
                elif os.path.isdir(item_path):
                    shutil.rmtree(item_path)

            # Verify Makefile is deleted
            self.assertFalse(os.path.exists(os.path.join(tmpdir, "Makefile")),
                           f"Makefile should be deleted for {repo_name}")

            # Run boil to restore files
            boil_result = subprocess.run(
                [boil_script, "make", "test"],
                cwd=tmpdir,
                capture_output=True,
                text=True,
                timeout=60
            )

            # Check that boil succeeded
            self.assertEqual(boil_result.returncode, 0,
                           f"Boil should succeed for {repo_name}. Output:\n{boil_result.stdout}\n{boil_result.stderr}")

            # Verify Makefile was restored
            self.assertTrue(os.path.exists(os.path.join(tmpdir, "Makefile")),
                          f"Makefile should be restored for {repo_name}")

            # Verify the test passes after restoration
            final_result = subprocess.run(["make", "test"], cwd=tmpdir, capture_output=True, text=True)
            self.assertEqual(final_result.returncode, 0,
                           f"Test should pass after restoration for {repo_name}. Output:\n{final_result.stdout}\n{final_result.stderr}")

            # Verify that boiled content matches the after/ folder
            example_after_dir = os.path.join(boiler_dir, "example_repos", repo_name, "after")
            if os.path.exists(example_after_dir):
                self._verify_after_is_subset_of_boiled(repo_name, example_after_dir, tmpdir)

    def _verify_after_is_subset_of_boiled(self, repo_name, after_dir, boiled_dir):
        """Verify that after/ is a subset of the boiled directory"""
        after_files = self._get_all_non_hidden_files(after_dir)
        boiled_files_rel = set(
            os.path.relpath(f, boiled_dir) 
            for f in self._get_all_non_hidden_files(boiled_dir)
        )

        # Check all files in after/ exist in boiled
        for after_file in after_files:
            relative_path = os.path.relpath(after_file, after_dir)
            if relative_path not in boiled_files_rel:
                msg = f"\n{'='*70}\n"
                msg += f"[{repo_name}] FILE IN after/ NOT FOUND IN BOILED RESULT\n"
                msg += f"{'='*70}\n"
                msg += f"File: {relative_path}\n\n"
                msg += f"Files in after/:\n"
                after_files_rel = sorted(os.path.relpath(f, after_dir) for f in after_files)
                for f in after_files_rel:
                    msg += f"  - {f}\n"
                msg += f"\nFiles in boiled result:\n"
                for f in sorted(boiled_files_rel):
                    msg += f"  - {f}\n"
                msg += f"{'='*70}\n"
                self.fail(msg)

            # Check file content line-by-line
            boiled_file = os.path.join(boiled_dir, relative_path)
            with open(after_file, 'r', errors='ignore') as f:
                after_lines = f.readlines()
            with open(boiled_file, 'r', errors='ignore') as f:
                boiled_lines = f.readlines()

            # All lines in after/ should exist in boiled/ in the same order
            boiled_idx = 0
            for after_idx, after_line in enumerate(after_lines):
                found = False
                for idx in range(boiled_idx, len(boiled_lines)):
                    if boiled_lines[idx] == after_line:
                        boiled_idx = idx + 1
                        found = True
                        break

                if not found:
                    msg = f"\n{'='*70}\n"
                    msg += f"[{repo_name}] LINE IN after/ NOT FOUND IN BOILED RESULT\n"
                    msg += f"{'='*70}\n"
                    msg += f"File: {relative_path}\n"
                    msg += f"Problem at line {after_idx + 1} in after/:\n"
                    msg += f"  {after_line.rstrip()}\n\n"
                    msg += f"after/{relative_path}:\n"
                    for i, line in enumerate(after_lines, 1):
                        mark = " <-- MISSING FROM BOILED" if i == after_idx + 1 else ""
                        msg += f"  {i:3d}: {line.rstrip()}{mark}\n"
                    msg += f"\nBoiled {relative_path} (relevant section):\n"
                    for i, line in enumerate(boiled_lines, 1):
                        msg += f"  {i:3d}: {line.rstrip()}\n"
                    msg += f"{'='*70}\n"
                    self.fail(msg)

    def _get_all_non_hidden_files(self, directory):
        """Recursively get all non-hidden files in directory"""
        files = []
        for root, dirs, filenames in os.walk(directory):
            # Skip hidden directories
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            for filename in filenames:
                if not filename.startswith('.'):
                    files.append(os.path.join(root, filename))
        return files


if __name__ == "__main__":
    unittest.main()

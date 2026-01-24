#!/usr/bin/env python3
"""
Integration tests for example repositories.

These tests run boil on each example repo to verify the full pipeline works.
They are slow tests and can be skipped with SKIP_SLOW_TESTS=1.
"""

import os
import sys
import unittest

BOILER_DIR = os.path.dirname(os.path.dirname(__file__))
BOIL_SCRIPT = os.path.join(BOILER_DIR, "boil")

# Add parent directory to path for imports
sys.path.insert(0, BOILER_DIR)

from tests.test_utils import copy_and_boil


def is_slow_test_skipped():
    """Check if slow tests should be skipped"""
    return os.environ.get("SKIP_SLOW_TESTS", "").lower() in ("1", "true", "yes")


class TestExampleRepos(unittest.TestCase):
    """Test boil on example repositories"""

    @classmethod
    def setUpClass(cls):
        """Find example repos directory"""
        cls.example_repos_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "example_repos"
        )

    def _get_example_repo_path(self, repo_name):
        """Get path to example repo's before/ directory"""
        return os.path.join(self.example_repos_dir, repo_name, "before")

    def _test_example_repo(self, repo_name, timeout=120):
        """Test that boil can restore a deleted example repo"""
        before_dir = self._get_example_repo_path(repo_name)

        if not os.path.exists(before_dir):
            self.skipTest(f"Example repo {repo_name} not found at {before_dir}")

        with copy_and_boil(
            src_dir=before_dir,
            test_command=["make", "test"],
            preserve_tmpdir=False,
            verify_before=True,
            delete_files=True,
            timeout=timeout
        ) as result:
            self.assertTrue(
                result['success'],
                f"Boil failed for {repo_name}:\n"
                f"stdout: {result['boil_result'].stdout[-1000:]}\n"
                f"stderr: {result['boil_result'].stderr[-1000:]}"
            )

    @unittest.skipIf(is_slow_test_skipped(), "Skipping slow test")
    def test_dim_repo(self):
        """Test boil on dim example repo"""
        self._test_example_repo("dim", timeout=180)

    @unittest.skipIf(is_slow_test_skipped(), "Skipping slow test")
    def test_simple_repo(self):
        """Test boil on simple example repo"""
        self._test_example_repo("simple", timeout=60)

    @unittest.skipIf(is_slow_test_skipped(), "Skipping slow test")
    def test_tree_sitter_repo(self):
        """Test boil on tree-sitter example repo"""
        self._test_example_repo("tree-sitter", timeout=180)

    @unittest.skipIf(is_slow_test_skipped(), "Skipping slow test")
    def test_tricky_repo(self):
        """Test boil on tricky example repo"""
        self._test_example_repo("tricky", timeout=60)

class TestBoilSearch(unittest.TestCase):
    """Test boil --search command"""

    @unittest.skipIf(is_slow_test_skipped(), "Skipping slow test")
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

    @unittest.skipIf(is_slow_test_skipped(), "Skipping slow test")
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

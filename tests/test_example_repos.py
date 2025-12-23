#!/usr/bin/env python3
"""
Integration tests for example repositories.

These tests run boil on each example repo to verify the full pipeline works.
They are slow tests and can be skipped with SKIP_SLOW_TESTS=1.
"""

import os
import sys
import unittest

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

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


if __name__ == "__main__":
    unittest.main()

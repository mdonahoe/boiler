"""
Test integrity checks to prevent AI agents from cheating by modifying tests.

This test only runs during 'make check' (when CHECK_MODE=1 is set).
It ensures that test files haven't been modified from their committed state.
"""

import os
import subprocess
import unittest


class TestIntegrity(unittest.TestCase):
    """
    Verify that test files haven't been modified.

    This prevents AI agents from "cheating" by relaxing test constraints
    instead of fixing the actual code.
    """

    def setUp(self):
        """Skip these tests unless CHECK_MODE is set."""
        if not os.environ.get('CHECK_MODE'):
            self.skipTest("Test integrity checks only run during 'make check'")

    def test_no_modified_tests(self):
        """
        Fail if any files in tests/ have been modified from git HEAD.

        This catches AI agents that try to weaken tests instead of fixing code.
        """
        try:
            # Check for modified files in tests/
            result = subprocess.run(
                ['git', 'diff', '--name-only', 'tests/'],
                capture_output=True,
                text=True,
                check=True
            )

            modified_files = [f for f in result.stdout.strip().split('\n') if f]

            if modified_files:
                error_msg = "\n\n" + "="*70 + "\n"
                error_msg += "INTEGRITY CHECK FAILED: Test files have been modified!\n"
                error_msg += "="*70 + "\n\n"
                error_msg += "Modified test files:\n"
                for f in modified_files:
                    error_msg += f"  - {f}\n"
                error_msg += "\n"
                error_msg += "Tests should not be modified to make them pass.\n"
                error_msg += "Instead, fix the implementation code to satisfy the tests.\n\n"
                error_msg += "If you legitimately need to update tests, commit them first,\n"
                error_msg += "then make your implementation changes.\n"
                error_msg += "="*70 + "\n"

                self.fail(error_msg)

        except subprocess.CalledProcessError as e:
            # If git command fails, skip the test (e.g., not in a git repo)
            self.skipTest(f"Git command failed: {e}")

    def test_no_staged_test_changes(self):
        """
        Fail if any files in tests/ have been staged but not committed.

        This catches attempts to stage test modifications.
        """
        try:
            # Check for staged files in tests/
            result = subprocess.run(
                ['git', 'diff', '--cached', '--name-only', 'tests/'],
                capture_output=True,
                text=True,
                check=True
            )

            staged_files = [f for f in result.stdout.strip().split('\n') if f]

            if staged_files:
                error_msg = "\n\n" + "="*70 + "\n"
                error_msg += "INTEGRITY CHECK FAILED: Test files have been staged!\n"
                error_msg += "="*70 + "\n\n"
                error_msg += "Staged test files:\n"
                for f in staged_files:
                    error_msg += f"  - {f}\n"
                error_msg += "\n"
                error_msg += "Commit test changes separately before making implementation changes.\n"
                error_msg += "="*70 + "\n"

                self.fail(error_msg)

        except subprocess.CalledProcessError as e:
            self.skipTest(f"Git command failed: {e}")


if __name__ == '__main__':
    unittest.main()

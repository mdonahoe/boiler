#!/usr/bin/env python3
"""
Test that the executor properly validates restorations and doesn't loop.
"""

import os
import sys
import tempfile
import subprocess
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from pipeline.executors.git_restore import GitRestoreExecutor
from pipeline.models import RepairPlan, ErrorClue


class ExecutorValidationTest(unittest.TestCase):
    """Test executor validation behavior"""

    def test_no_changes_detection(self):
        """Test that executor detects when restoration doesn't change anything"""
        executor = GitRestoreExecutor()

        # Create a fake plan for a file that already exists
        plan = RepairPlan(
            plan_type="restore_file",
            priority=0,
            target_file="test.py",  # File that already exists in boiler repo
            action="restore_full",
            params={"ref": "HEAD"},
            reason="Test restoration",
            clue_source=ErrorClue(
                clue_type="test",
                confidence=1.0,
                context={},
                source_line="test"
            )
        )

        # Try to restore it
        result = executor.execute(plan)

        # Should fail because file already matches git
        self.assertFalse(result.success, "Executor should have detected file already matches")

    def test_validation_prevents_missing_file(self):
        """Test that validation rejects files not in git"""
        executor = GitRestoreExecutor()

        plan = RepairPlan(
            plan_type="restore_file",
            priority=0,
            target_file="nonexistent_file_xyz123.py",
            action="restore_full",
            params={"ref": "HEAD"},
            reason="Test restoration",
            clue_source=ErrorClue(
                clue_type="test",
                confidence=1.0,
                context={},
                source_line="test"
            )
        )

        # Validation should fail
        is_valid, error_msg = executor.validate_plan(plan)

        self.assertFalse(is_valid, "Validation should have rejected nonexistent file")


if __name__ == "__main__":
    unittest.main()

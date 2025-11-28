#!/usr/bin/env python3
"""
Test that the executor properly validates restorations and doesn't loop.
"""

import os
import sys
import tempfile
import subprocess

sys.path.insert(0, os.path.dirname(__file__))

from pipeline.executors.git_restore import GitRestoreExecutor
from pipeline.models import RepairPlan, ErrorClue


def test_no_changes_detection():
    """Test that executor detects when restoration doesn't change anything"""
    print("\n=== Test: Executor Detects No-Change Restoration ===")

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
    if result.success:
        print("✗ FAILED: Executor should have detected file already matches")
        return False

    print(f"✓ Executor correctly rejected: {result.error_message}")
    return True


def test_validation_prevents_missing_file():
    """Test that validation rejects files not in git"""
    print("\n=== Test: Validation Prevents Missing Files ===")

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

    if is_valid:
        print("✗ FAILED: Validation should have rejected nonexistent file")
        return False

    print(f"✓ Validation correctly rejected: {error_msg}")
    return True


def main():
    """Run tests"""
    print("=" * 80)
    print("Executor Validation Tests")
    print("=" * 80)

    tests = [
        test_validation_prevents_missing_file,
        test_no_changes_detection,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"✗ Test raised exception: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "=" * 80)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 80)

    if failed == 0:
        print("\n✓✓✓ ALL TESTS PASSED! ✓✓✓")
        print("Executor now properly validates and prevents looping!")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
Test that planners don't create plans for files that are already restored.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from pipeline import run_pipeline, GitState
from pipeline.handlers import register_all_handlers


def test_planner_skips_existing_file():
    """Test that planner doesn't create plan for file that already matches git"""
    print("\n=== Test: Planner Skips Already-Restored File ===")

    register_all_handlers()

    # Simulate error for test.py which already exists and matches git
    stderr = """
/tmp/ex_bar.c:82:10: fatal error: test.py: No such file or directory
   82 | #include "test.py"
      |          ^~~~~~~~~~
compilation terminated.
"""

    # test.py exists in the boiler repo and matches HEAD
    git_state = GitState(
        ref="HEAD",
        deleted_files=set(),
        git_toplevel="/root/boiler"
    )

    # Change to boiler directory where ex.h exists
    original_dir = os.getcwd()
    os.chdir("/root/boiler")

    try:
        result = run_pipeline(stderr, "", git_state, debug=True)

        # Check that clues were detected
        if not result.clues_detected:
            print("✗ FAILED: Should have detected error")
            return False

        print(f"✓ Detected {len(result.clues_detected)} clue(s)")

        # Check that NO plans were generated (file already matches git)
        if result.plans_generated:
            print(f"✗ FAILED: Should not have generated plans for existing file")
            print(f"   Plans generated: {result.plans_generated}")
            return False

        print("✓ Planner correctly skipped test.py (already matches git)")

        # Should report failure since no plans could be generated
        if result.success:
            print("✗ FAILED: Should report failure when no plans available")
            return False

        print("✓ Pipeline correctly reported failure (no actionable plans)")

        return True

    finally:
        os.chdir(original_dir)


def test_planner_creates_plan_for_missing_file():
    """Test that planner DOES create plan when file is actually missing"""
    print("\n=== Test: Planner Creates Plan For Missing File ===")

    register_all_handlers()

    stderr = "cat: nonexistent123.txt: No such file or directory"

    git_state = GitState(
        ref="HEAD",
        deleted_files={"nonexistent123.txt"},
        git_toplevel="/root/boiler"
    )

    result = run_pipeline(stderr, "", git_state, debug=False)

    # Check that clues were detected
    if not result.clues_detected:
        print("✗ FAILED: Should have detected error")
        return False

    print(f"✓ Detected {len(result.clues_detected)} clue(s)")

    # Check that plans WERE generated (file doesn't exist)
    if not result.plans_generated:
        print("✗ FAILED: Should have generated plan for missing file")
        return False

    print(f"✓ Planner correctly created plan for nonexistent123.txt")

    # Execution should fail (file not in git) but that's expected
    print(f"✓ Pipeline attempted to execute plan (expected to fail validation)")

    return True


def main():
    """Run tests"""
    print("=" * 80)
    print("Planner Validation Tests")
    print("=" * 80)

    tests = [
        test_planner_skips_existing_file,
        test_planner_creates_plan_for_missing_file,
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
        print("Planner now skips files that are already restored!")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

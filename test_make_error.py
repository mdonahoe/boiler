#!/usr/bin/env python3
"""
Test that make missing target errors are detected and planned.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from pipeline import run_pipeline, GitState
from pipeline.handlers import register_all_handlers


def test_make_missing_target():
    """Test detection of make missing target error"""
    print("\n=== Test: Make Missing Target Detection ===")

    # Register handlers
    register_all_handlers()

    # Use the actual error from /root/dim/.boil/iter1.exit2.txt
    stderr = """make: *** No rule to make target 'dim.c', needed by 'dim'.  Stop.
"""

    git_state = GitState(
        ref="HEAD",
        deleted_files={"dim.c"},  # Simulate that dim.c is deleted
        git_toplevel="/root/dim"
    )

    result = run_pipeline(stderr, "", git_state, debug=True)

    print("\n" + "=" * 80)
    print("RESULTS")
    print("=" * 80)
    print(f"Success: {result.success}")
    print(f"Clues detected: {len(result.clues_detected or [])}")
    print(f"Plans generated: {len(result.plans_generated or [])}")
    print(f"Files modified: {result.files_modified}")

    if result.clues_detected:
        print("\nClues:")
        for clue in result.clues_detected:
            print(f"  - {clue.clue_type}: {clue.context}")

    if result.plans_generated:
        print("\nPlans:")
        for plan in result.plans_generated:
            print(f"  - [{plan.priority}] {plan.action} on {plan.target_file}")
            print(f"    Reason: {plan.reason}")

    # Verify detection worked
    if not result.clues_detected:
        print("\n✗ FAILED: No clues detected")
        return False

    if result.clues_detected[0].clue_type != "make_missing_target":
        print(f"\n✗ FAILED: Wrong clue type: {result.clues_detected[0].clue_type}")
        return False

    if not result.plans_generated:
        print("\n✗ FAILED: No plans generated")
        return False

    # Check that we have a plan to restore dim.c
    has_dim_c_plan = any(
        "dim.c" in plan.target_file
        for plan in result.plans_generated
    )

    if not has_dim_c_plan:
        print("\n✗ FAILED: No plan to restore dim.c")
        return False

    print("\n✓✓✓ Test PASSED! ✓✓✓")
    print("The pipeline can now handle make missing target errors!")
    return True


if __name__ == "__main__":
    try:
        success = test_make_missing_target()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ Test raised exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

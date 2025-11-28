#!/usr/bin/env python3
"""
Simple test to verify the pipeline system works.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(__file__))

from pipeline import run_pipeline, GitState
from pipeline.handlers import register_all_handlers


def test_permission_denied_detection():
    """Test that permission denied errors are detected and planned"""
    print("\n=== Test 1: Permission Denied Detection ===")

    # Register handlers
    register_all_handlers()

    # Simulate a permission denied error
    stderr = """
PermissionError: [Errno 13] Permission denied: './test.py'
"""

    git_state = GitState(
        ref="HEAD",
        deleted_files=set(),
        git_toplevel="/root/boiler"
    )

    result = run_pipeline(stderr, "", git_state, debug=True)

    if result.success:
        print("✓ Test passed: Pipeline successfully handled permission error")
    else:
        print("✗ Test failed: Pipeline did not handle permission error")
        print(f"   Error: {result.error_message}")

    return result.success


def test_no_error():
    """Test that pipeline returns gracefully when no errors detected"""
    print("\n=== Test 2: No Error Detection ===")

    # Register handlers
    register_all_handlers()

    # No error messages
    stderr = "Everything is fine!"
    stdout = "Tests passed!"

    git_state = GitState(
        ref="HEAD",
        deleted_files=set(),
        git_toplevel="/root/boiler"
    )

    result = run_pipeline(stderr, stdout, git_state, debug=True)

    if not result.success and "No error clues detected" in (result.error_message or ""):
        print("✓ Test passed: Pipeline correctly reported no errors")
        return True
    else:
        print("✗ Test failed: Pipeline should have reported no errors")
        return False


def test_missing_file_in_git():
    """Test validation catches files that don't exist in git"""
    print("\n=== Test 3: Missing File Validation ===")

    # Register handlers
    register_all_handlers()

    # Permission error for a file that definitely doesn't exist in git
    stderr = """
PermissionError: [Errno 13] Permission denied: './nonexistent_file_xyz123.py'
"""

    git_state = GitState(
        ref="HEAD",
        deleted_files=set(),
        git_toplevel="/root/boiler"
    )

    result = run_pipeline(stderr, "", git_state, debug=True)

    # Should fail because file doesn't exist in git
    if not result.success:
        print("✓ Test passed: Pipeline correctly rejected nonexistent file")
        return True
    else:
        print("✗ Test failed: Pipeline should have rejected nonexistent file")
        return False


def main():
    """Run all tests"""
    print("=" * 80)
    print("Pipeline System Tests")
    print("=" * 80)

    tests = [
        test_permission_denied_detection,
        test_no_error,
        test_missing_file_in_git,
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

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

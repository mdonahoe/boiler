#!/usr/bin/env python3
"""
Test that file error detectors work with actual errors from heirloom-ex-vi.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from pipeline import run_pipeline, GitState
from pipeline.handlers import register_all_handlers


def test_file_not_found():
    """Test FileNotFoundError detection"""
    print("\n=== Test 1: FileNotFoundError ===")
    register_all_handlers()

    stderr = "FileNotFoundError: [Errno 2] No such file or directory: './test.sh'"
    git_state = GitState(ref="HEAD", deleted_files=set(), git_toplevel="/root/boiler")

    result = run_pipeline(stderr, "", git_state, debug=False)

    assert len(result.clues_detected or []) > 0, "Should detect FileNotFoundError"
    assert result.clues_detected[0].clue_type == "missing_file"
    assert result.clues_detected[0].context["file_path"] == "./test.sh"
    print(f"✓ Detected: {result.clues_detected[0].context['file_path']}")
    return True


def test_shell_cannot_open():
    """Test sh cannot open detection"""
    print("\n=== Test 2: Shell Cannot Open ===")
    register_all_handlers()

    stderr = "sh: 0: cannot open makeoptions: No such file"
    git_state = GitState(ref="HEAD", deleted_files=set(), git_toplevel="/root/boiler")

    result = run_pipeline(stderr, "", git_state, debug=False)

    assert len(result.clues_detected or []) > 0, "Should detect sh cannot open"
    assert result.clues_detected[0].clue_type == "missing_file"
    assert result.clues_detected[0].context["file_path"] == "makeoptions"
    print(f"✓ Detected: {result.clues_detected[0].context['file_path']}")
    return True


def test_shell_command_not_found():
    """Test shell command not found detection"""
    print("\n=== Test 3: Shell Command Not Found ===")
    register_all_handlers()

    stderr = "./test.sh: line 3: ./configure: No such file or directory"
    git_state = GitState(ref="HEAD", deleted_files=set(), git_toplevel="/root/boiler")

    result = run_pipeline(stderr, "", git_state, debug=False)

    assert len(result.clues_detected or []) > 0, "Should detect command not found"
    assert result.clues_detected[0].clue_type == "missing_file"
    assert result.clues_detected[0].context["file_path"] == "configure"
    print(f"✓ Detected: {result.clues_detected[0].context['file_path']}")
    return True


def test_cat_no_such_file():
    """Test cat no such file detection"""
    print("\n=== Test 4: Cat No Such File ===")
    register_all_handlers()

    stderr = "cat: Makefile.in: No such file or directory"
    git_state = GitState(ref="HEAD", deleted_files=set(), git_toplevel="/root/boiler")

    result = run_pipeline(stderr, "", git_state, debug=False)

    assert len(result.clues_detected or []) > 0, "Should detect cat error"
    assert result.clues_detected[0].clue_type == "missing_file"
    assert result.clues_detected[0].context["file_path"] == "Makefile.in"
    print(f"✓ Detected: {result.clues_detected[0].context['file_path']}")
    return True


def test_diff_no_such_file():
    """Test diff no such file detection"""
    print("\n=== Test 5: Diff No Such File ===")
    register_all_handlers()

    stderr = "diff: test.txt: No such file or directory"
    git_state = GitState(ref="HEAD", deleted_files=set(), git_toplevel="/root/boiler")

    result = run_pipeline(stderr, "", git_state, debug=False)

    assert len(result.clues_detected or []) > 0, "Should detect diff error"
    assert result.clues_detected[0].clue_type == "missing_file"
    assert result.clues_detected[0].context["file_path"] == "test.txt"
    print(f"✓ Detected: {result.clues_detected[0].context['file_path']}")
    return True


def test_c_compilation_error():
    """Test C compilation error detection"""
    print("\n=== Test 6: C Compilation Error ===")
    register_all_handlers()

    stderr = """/tmp/ex_bar502220.c:82:10: fatal error: ex.h: No such file or directory
   82 | #include "ex.h"
      |          ^~~~~~
compilation terminated."""
    git_state = GitState(ref="HEAD", deleted_files=set(), git_toplevel="/root/boiler")

    result = run_pipeline(stderr, "", git_state, debug=False)

    assert len(result.clues_detected or []) > 0, "Should detect C compilation error"
    assert result.clues_detected[0].clue_type == "missing_file"
    assert result.clues_detected[0].context["file_path"] == "ex.h"
    assert result.clues_detected[0].context["is_header"] == True
    print(f"✓ Detected: {result.clues_detected[0].context['file_path']}")
    return True


def main():
    """Run all tests"""
    print("=" * 80)
    print("File Error Detection Tests")
    print("=" * 80)

    tests = [
        test_file_not_found,
        test_shell_cannot_open,
        test_shell_command_not_found,
        test_cat_no_such_file,
        test_diff_no_such_file,
        test_c_compilation_error,
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
        print("All file error detectors are working correctly!")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

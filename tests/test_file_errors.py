#!/usr/bin/env python3
"""
Test that file error detectors work with actual errors from heirloom-ex-vi.
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from pipeline import run_pipeline, GitState
from pipeline.handlers import register_all_handlers


class FileErrorDetectionTest(unittest.TestCase):
    """Test file error detection"""

    def setUp(self):
        """Register handlers before each test"""
        register_all_handlers()

    def test_file_not_found(self):
        """Test FileNotFoundError detection"""
        stderr = "FileNotFoundError: [Errno 2] No such file or directory: './test.sh'"
        git_state = GitState(ref="HEAD", deleted_files=set(), git_toplevel="/root/boiler")

        result = run_pipeline(stderr, "", git_state, debug=False)

        self.assertIsNotNone(result.clues_detected, "Should detect FileNotFoundError")
        self.assertGreater(len(result.clues_detected), 0, "Should have at least one clue")
        self.assertEqual(result.clues_detected[0].clue_type, "missing_file")
        self.assertEqual(result.clues_detected[0].context["file_path"], "./test.sh")

    def test_shell_cannot_open(self):
        """Test sh cannot open detection"""
        stderr = "sh: 0: cannot open makeoptions: No such file"
        git_state = GitState(ref="HEAD", deleted_files=set(), git_toplevel="/root/boiler")

        result = run_pipeline(stderr, "", git_state, debug=False)

        self.assertIsNotNone(result.clues_detected, "Should detect sh cannot open")
        self.assertGreater(len(result.clues_detected), 0, "Should have at least one clue")
        self.assertEqual(result.clues_detected[0].clue_type, "missing_file")
        self.assertEqual(result.clues_detected[0].context["file_path"], "makeoptions")

    def test_shell_command_not_found(self):
        """Test shell command not found detection"""
        stderr = "./test.sh: line 3: ./configure: No such file or directory"
        git_state = GitState(ref="HEAD", deleted_files=set(), git_toplevel="/root/boiler")

        result = run_pipeline(stderr, "", git_state, debug=False)

        self.assertIsNotNone(result.clues_detected, "Should detect command not found")
        self.assertGreater(len(result.clues_detected), 0, "Should have at least one clue")
        self.assertEqual(result.clues_detected[0].clue_type, "missing_file")
        self.assertEqual(result.clues_detected[0].context["file_path"], "configure")

    def test_cat_no_such_file(self):
        """Test cat no such file detection"""
        stderr = "cat: Makefile.in: No such file or directory"
        git_state = GitState(ref="HEAD", deleted_files=set(), git_toplevel="/root/boiler")

        result = run_pipeline(stderr, "", git_state, debug=False)

        self.assertIsNotNone(result.clues_detected, "Should detect cat error")
        self.assertGreater(len(result.clues_detected), 0, "Should have at least one clue")
        self.assertEqual(result.clues_detected[0].clue_type, "missing_file")
        self.assertEqual(result.clues_detected[0].context["file_path"], "Makefile.in")

    def test_diff_no_such_file(self):
        """Test diff no such file detection"""
        stderr = "diff: test.txt: No such file or directory"
        git_state = GitState(ref="HEAD", deleted_files=set(), git_toplevel="/root/boiler")

        result = run_pipeline(stderr, "", git_state, debug=False)

        self.assertIsNotNone(result.clues_detected, "Should detect diff error")
        self.assertGreater(len(result.clues_detected), 0, "Should have at least one clue")
        self.assertEqual(result.clues_detected[0].clue_type, "missing_file")
        self.assertEqual(result.clues_detected[0].context["file_path"], "test.txt")

    def test_c_compilation_error(self):
        """Test C compilation error detection"""
        stderr = """/tmp/ex_bar502220.c:82:10: fatal error: ex.h: No such file or directory
   82 | #include "ex.h"
       |          ^~~~~~
compilation terminated."""
        git_state = GitState(ref="HEAD", deleted_files=set(), git_toplevel="/root/boiler")

        result = run_pipeline(stderr, "", git_state, debug=False)

        self.assertIsNotNone(result.clues_detected, "Should detect C compilation error")
        self.assertGreater(len(result.clues_detected), 0, "Should have at least one clue")
        self.assertEqual(result.clues_detected[0].clue_type, "missing_file")
        self.assertEqual(result.clues_detected[0].context["file_path"], "ex.h")


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""
Tests for C/C++ compilation and linker error detection and planning.
"""

import unittest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.handlers import register_all_handlers
from pipeline.detectors.file_errors import CCompilationErrorDetector, CLinkerErrorDetector, FopenNoSuchFileDetector
from pipeline.models import ErrorClue, GitState
from pipeline.planners.file_restore import MissingFilePlanner, LinkerUndefinedSymbolsPlanner


class TestCCompilationErrorDetector(unittest.TestCase):
    def setUp(self):
        register_all_handlers()
        self.detector = CCompilationErrorDetector()

    def test_detect_missing_header_simple(self):
        """Test detection of simple missing header error"""
        err = """lib/src/node.c:2:10: fatal error: ./point.h: No such file or directory
    2 | #include "./point.h"
      |          ^~~~~~~~~~~
compilation terminated."""
        
        clues = self.detector.detect(err)
        self.assertEqual(len(clues), 1)
        self.assertEqual(clues[0].clue_type, "missing_file")
        self.assertEqual(clues[0].context["file_path"], "point.h")

    def test_detect_with_source_context(self):
        """Test that detector extracts source file context"""
        err = """cc -O3 -Wall -Ilib/src -c -o lib/src/node.o lib/src/node.c
lib/src/node.c:2:10: fatal error: ./point.h: No such file or directory
    2 | #include "./point.h"
      |          ^~~~~~~~~~~
compilation terminated."""

        clues = self.detector.detect(err)
        self.assertEqual(len(clues), 1)
        # Simplified detector now only extracts file_path
        self.assertEqual(clues[0].context["file_path"], "point.h")

    def test_detect_with_relative_path(self):
        """Test detection with ./ prefix"""
        err = """cc -o tree_print tree_print.c
tree_print.c:2:10: fatal error: ./language.h: No such file or directory"""
        
        clues = self.detector.detect(err)
        self.assertEqual(len(clues), 1)
        self.assertEqual(clues[0].context["file_path"], "language.h")


class TestCLinkerErrorDetector(unittest.TestCase):
    def setUp(self):
        register_all_handlers()
        self.detector = CLinkerErrorDetector()

    def test_detect_undefined_references(self):
        """Test detection of undefined reference errors"""
        err = """/usr/bin/ld: /tmp/cckoAdDP.o: in function `main':
tree_print.c:(.text+0x28a): undefined reference to `ts_parser_new'
/usr/bin/ld: tree_print.c:(.text+0x2f1): undefined reference to `ts_parser_set_language'
collect2: error: ld returned 1 exit status"""

        clues = self.detector.detect(err)
        self.assertEqual(len(clues), 2)  # Now emits one clue per symbol
        self.assertEqual(clues[0].clue_type, "linker_undefined_symbols")
        self.assertEqual(clues[1].clue_type, "linker_undefined_symbols")
        symbols = [clues[0].context["symbol"], clues[1].context["symbol"]]
        self.assertIn("ts_parser_new", symbols)
        self.assertIn("ts_parser_set_language", symbols)

    def test_detect_missing_library(self):
        """Test detection of missing library errors"""
        err = """/usr/bin/ld: cannot find -lsomelibrary: No such file or directory"""

        clues = self.detector.detect(err)
        self.assertEqual(len(clues), 1)
        self.assertEqual(clues[0].clue_type, "missing_file")
        self.assertEqual(clues[0].context["file_path"], "-lsomelibrary")

    def test_detect_missing_object_file(self):
        """Test detection of missing object file errors"""
        err = """/usr/bin/ld: cannot find exrecover.o: No such file or directory"""

        clues = self.detector.detect(err)
        self.assertEqual(len(clues), 1)
        self.assertEqual(clues[0].clue_type, "missing_file")
        self.assertEqual(clues[0].context["file_path"], "exrecover.o")


class TestMissingFilePlanner(unittest.TestCase):
    def setUp(self):
        register_all_handlers()
        self.planner = MissingFilePlanner()

    def test_plan_with_source_dir_context(self):
        """Test that planner uses source_dir context to find files"""
        clue = ErrorClue(
            clue_type="missing_file",
            confidence=1.0,
            context={
                "file_path": "point.h",
                "is_header": True,
                "source_file": "lib/src/node.c",
                "source_dir": "lib/src"
            },
            source_line="fatal error: ./point.h: No such file or directory"
        )
        
        # Mock git state
        git_state = GitState(
            ref="HEAD",
            deleted_files={"lib/src/point.h"},
            git_toplevel="/repo"
        )
        
        plans = self.planner.plan([clue], git_state)
        self.assertEqual(len(plans), 1)
        # Should use the actual path found in deleted files
        self.assertEqual(plans[0].target_file, "lib/src/point.h")


class TestFopenErrorDetector(unittest.TestCase):
    def setUp(self):
        register_all_handlers()
        self.detector = FopenNoSuchFileDetector()

    def test_detect_assertion_error_with_fopen(self):
        """Test detection of AssertionError with fopen error"""
        err = """AssertionError: 'example.py' not found in 'fopen: No such file or directory' : Should show the filename"""

        clues = self.detector.detect(err)
        self.assertEqual(len(clues), 1)
        self.assertEqual(clues[0].clue_type, "missing_file_assertion")
        self.assertEqual(clues[0].context["file_path"], "example.py")

    def test_detect_simple_fopen_error(self):
        """Test detection of simple fopen error with filename"""
        err = """fopen: config.txt: No such file or directory"""
        
        clues = self.detector.detect(err)
        self.assertEqual(len(clues), 1)
        self.assertEqual(clues[0].context["file_path"], "config.txt")

    def test_detect_fallback_py_file(self):
        """Test fallback detection when filename not explicit - no longer supported"""
        err = """Test failure: Expected 'def test_function' in 'test.py'
fopen: No such file or directory"""

        clues = self.detector.detect(err)
        # Simplified detector no longer handles fallback/inference
        self.assertEqual(len(clues), 0)


class TestLinkerUndefinedSymbolsPlanner(unittest.TestCase):
    def setUp(self):
        register_all_handlers()
        self.planner = LinkerUndefinedSymbolsPlanner()

    def test_plan_finds_lib_c(self):
        """Test that planner identifies lib.c as priority for undefined symbols"""
        clue = ErrorClue(
            clue_type="linker_undefined_symbols",
            confidence=1.0,
            context={"symbols": ["ts_parser_new", "ts_tree_delete"]},
            source_line="Found 2 undefined references"
        )
        
        git_state = GitState(
            ref="HEAD",
            deleted_files={"lib/src/lib.c"},
            git_toplevel="/repo"
        )
        
        plans = self.planner.plan([clue], git_state)
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0].target_file, "lib/src/lib.c")
        self.assertIn("lib.c", plans[0].reason)


if __name__ == '__main__':
    unittest.main()

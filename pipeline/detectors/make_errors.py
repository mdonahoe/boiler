"""
Detectors for make/build system errors.
"""

import re
import typing as T
from pipeline.detectors.base import Detector
from pipeline.models import ErrorClue


class MakeEnteringDirectoryDetector(Detector):
    """
    Detect when make has entered a directory.
    Useful for understanding context for later make errors
    """
    PATTERNS = {
        "make_enter_directory": r"make(?:\[\d+\])?: Entering directory '(?P<directory>[^']+)'"
    }

    EXAMPLES = [
        (
            "make: Entering directory 'helpers'",
            {
                "clue_type": "make_enter_directory",
                "confidence": 1.0,
                "context": {
                    "directory": "helpers",
                },
            },
        ),
    ]


class MakeMissingTargetDetector(Detector):
    """
    Detect make errors when a required source file is missing.

    Matches patterns like:
    - make: *** No rule to make target 'dim.c', needed by 'dim'.  Stop.
    - make[1]: *** No rule to make target 'src/file.c', needed by 'target'.  Stop.
    """


    PATTERNS = {
        "make_missing_target": r"No rule to make target '(?P<target>[^']+)', needed by '(?P<needed_by>[^']+)'",
    }

    EXAMPLES = [
        (
            "make: *** No rule to make target 'dim.c', needed by 'dim'.  Stop.",
            {
                "clue_type": "make_missing_target",
                "confidence": 1.0,
                "context": {
                    "target": "dim.c",
                    "needed_by": "dim",
                },
            },
        ),
        (
            "make[1]: *** No rule to make target 'src/file.c', needed by 'target'.  Stop.",
            {
                "clue_type": "make_missing_target",
                "confidence": 1.0,
                "context": {
                    "target": "src/file.c",
                    "needed_by": "target",
                },
            },
        ),
    ]



class MakeNoRuleDetector(Detector):
    """
    Detect make errors when no rule exists for a target (often means Makefile is missing).

    Matches patterns like:
    - make: *** No rule to make target 'test'.  Stop.
    """

    PATTERNS = {
        "make_no_rule": r"make(?:\[\d+\])?: \*\*\* No rule to make target '(?P<target>[^']+)'\.\s+Stop\.",
    }

    EXAMPLES = [
        (
            "make: *** No rule to make target 'test'.  Stop.",
            {
                "clue_type": "make_no_rule",
                "confidence": 1.0,
                "context": {
                    "target": "test",
                },
            },
        ),
    ]


class MakeGlobPatternErrorDetector(Detector):
    """
    Detect make errors when a glob pattern file/directory is missing.

    Matches patterns like:
    - make[2]: *** tests: No such file or directory.  Stop.
    - make: *** src/*.c: No such file or directory.  Stop.

    This is different from MakeMissingTargetDetector which has the "needed by" clause.
    """

    PATTERNS = {
        "missing_file": r"make(?:\[\d+\])?: \*\*\* (?P<file_path>[^:]+):\s+No such file or directory\.\s+Stop\.",
    }

    EXAMPLES = [
        (
            "make[2]: *** tests: No such file or directory.  Stop.",
            {
                "clue_type": "missing_file",
                "confidence": 1.0,
                "context": {
                    "file_path": "tests",
                },
            },
        ),
        (
            "make: *** src/*.c: No such file or directory.  Stop.",
            {
                "clue_type": "missing_file",
                "confidence": 1.0,
                "context": {
                    "file_path": "src/*.c",
                },
            },
        ),
    ]

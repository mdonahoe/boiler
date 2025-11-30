"""
Detectors for make/build system errors.
"""

import re
import typing as T
from pipeline.detectors.base import RegexDetector
from pipeline.models import ErrorClue


class MakeEnteringDirectoryDetector(RegexDetector):
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


class MakeMissingTargetDetector(RegexDetector):
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



class MakeNoRuleDetector(RegexDetector):
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

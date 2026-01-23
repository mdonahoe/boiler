"""
Detector for make missing target errors.
"""

import re
import typing as T
from pipeline.detectors.base import Detector
from pipeline.models import ErrorClue


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

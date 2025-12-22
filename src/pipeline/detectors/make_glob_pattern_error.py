"""
Detector for make glob pattern errors.
"""

import re
import typing as T
from src.pipeline.detectors.base import Detector
from src.pipeline.models import ErrorClue


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

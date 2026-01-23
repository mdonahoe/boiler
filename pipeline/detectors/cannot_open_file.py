"""
Detector for generic "Cannot open file" errors.
"""

import re
import typing as T
from pipeline.detectors.base import Detector
from pipeline.models import ErrorClue


class CannotOpenFileDetector(Detector):
    """
    Detect generic "Cannot open file" errors from programs.

    Matches patterns like:
    - Error: Cannot open file 'example.c'
    - Error: Cannot open file "example.py"
    - error: Cannot open file 'test.txt'
    """

    PATTERNS = {
        "missing_file": r"[Ee]rror:?\s+Cannot open file\s+['\"](?P<file_path>[^'\"]+)['\"]",
    }

    EXAMPLES = [
        (
            "Error: Cannot open file 'example.c'",
            {
                "clue_type": "missing_file",
                "confidence": 1.0,
                "context": {"file_path": "example.c"},
            },
        ),
        (
            "error: Cannot open file \"example.py\"",
            {
                "clue_type": "missing_file",
                "confidence": 1.0,
                "context": {"file_path": "example.py"},
            },
        ),
    ]

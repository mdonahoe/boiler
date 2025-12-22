"""
Detector for shell errors when a file cannot be opened.
"""

import re
import typing as T
from src.pipeline.detectors.base import Detector
from src.pipeline.models import ErrorClue


class ShellCannotOpenDetector(Detector):
    """
    Detect shell errors when a file cannot be opened.

    Matches patterns like:
    - sh: 0: cannot open makeoptions: No such file
    - /bin/sh: cannot open file: No such file
    """

    PATTERNS = {
        "missing_file": r"sh:\s*\d+:\s*cannot open\s+(?P<file_path>[^\s:]+):\s*No such file",
    }

    EXAMPLES = [
        (
            "sh: 0: cannot open makeoptions: No such file",
            {
                "clue_type": "missing_file",
                "confidence": 1.0,
                "context": {"file_path": "makeoptions"},
            },
        ),
    ]

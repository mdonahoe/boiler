"""
Detector for cat errors when a file is missing.
"""

import re
import typing as T
from pipeline.detectors.base import Detector
from pipeline.models import ErrorClue


class CatNoSuchFileDetector(Detector):
    """
    Detect cat errors when a file is missing.

    Matches patterns like:
    - cat: Makefile.in: No such file or directory
    """

    PATTERNS = {
        "missing_file": r"cat:\s*(?P<file_path>[^\s:]+):\s*No such file or directory",
    }

    EXAMPLES = [
        (
            "cat: Makefile.in: No such file or directory",
            {
                "clue_type": "missing_file",
                "confidence": 1.0,
                "context": {"file_path": "Makefile.in"},
            },
        ),
    ]

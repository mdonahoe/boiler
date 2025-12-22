"""
Detector for shell errors when a command/script is not found.
"""

import re
import typing as T
from src.pipeline.detectors.base import Detector
from src.pipeline.models import ErrorClue


class ShellCommandNotFoundDetector(Detector):
    """
    Detect shell errors when a command/script is not found.

    Matches patterns like:
    - ./test.sh: line 3: ./configure: No such file or directory
    - ./test.sh: 2: ./configure: not found
    - /bin/sh: ./script.sh: not found
    """

    PATTERNS = {
        "missing_file": r":\s*line\s+\d+:\s*\.?/?(?P<file_path>[^\s:]+):\s*No such file or directory",
        "missing_file_not_found": r":\s*\d+:\s*\.?/?(?P<file_path>[^\s:]+):\s*not found",
    }

    EXAMPLES = [
        (
            "./test.sh: line 3: ./configure: No such file or directory",
            {
                "clue_type": "missing_file",
                "confidence": 1.0,
                "context": {"file_path": "configure"},
            },
        ),
        (
            "./test.sh: 2: ./script.sh: not found",
            {
                "clue_type": "missing_file_not_found",
                "confidence": 1.0,
                "context": {"file_path": "script.sh"},
            },
        ),
    ]

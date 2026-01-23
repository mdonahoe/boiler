"""
Detector for FileNotFoundError exceptions.
"""

import re
import typing as T
from pipeline.detectors.base import Detector
from pipeline.models import ErrorClue


class FileNotFoundDetector(Detector):
    """
    Detect FileNotFoundError in various formats.

    Matches patterns like:
    - FileNotFoundError: [Errno 2] No such file or directory: './test.sh'
    - FileNotFoundError: ./test.sh
    """

    PATTERNS = {
        "missing_file": r"FileNotFoundError:.*?No such file or directory:\s*['\"](?P<file_path>[^'\"]+)['\"]",
        "missing_file_simple": r"FileNotFoundError:\s*(?P<file_path>[^\s:]+)",
    }

    EXAMPLES = [
        (
            "FileNotFoundError: [Errno 2] No such file or directory: './test.sh'",
            {
                "clue_type": "missing_file",
                "confidence": 1.0,
                "context": {"file_path": "./test.sh"},
            },
        ),
        (
            "FileNotFoundError: ./configure",
            {
                "clue_type": "missing_file_simple",
                "confidence": 1.0,
                "context": {"file_path": "./configure"},
            },
        ),
    ]

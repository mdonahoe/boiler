"""
Detector for fopen errors when a file cannot be opened.
"""

import re
import typing as T
from pipeline.detectors.base import Detector
from pipeline.models import ErrorClue


class FopenNoSuchFileDetector(Detector):
    """
    Detect fopen errors when a file cannot be opened.

    Matches patterns like:
    - fopen: No such file or directory
    - fopen: example.py: No such file or directory
    - AssertionError: 'example.py' not found in 'fopen: No such file or directory'
    """

    PATTERNS = {
        "missing_file": r"fopen:\s+(?P<file_path>[^\s:]+?):\s*No such file or directory",
        "missing_file_assertion": r"AssertionError:\s*['\"](?P<file_path>[^'\"]+\.(?:py|txt|md|c|h|cpp|hpp|json|yaml|yml|sh|rs|go|java|js|ts|html|css|xml|sql))['\"].*fopen:\s*No such file or directory",
    }

    EXAMPLES = [
        (
            "fopen: example.py: No such file or directory",
            {
                "clue_type": "missing_file",
                "confidence": 1.0,
                "context": {"file_path": "example.py"},
            },
        ),
        (
            "AssertionError: 'hello.py' not found in 'fopen: No such file or directory'",
            {
                "clue_type": "missing_file_assertion",
                "confidence": 1.0,
                "context": {"file_path": "hello.py"},
            },
        ),
    ]

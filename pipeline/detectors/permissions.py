"""
Detectors for permission-related errors.
"""

import re
import typing as T
from pipeline.detectors.base import RegexDetector
from pipeline.models import ErrorClue


class PermissionDeniedDetector(RegexDetector):
    """
    Detect permission denied errors.

    Matches patterns like:
    - PermissionError: [Errno 13] Permission denied: './test_tree_print.py'
    - Permission denied: './test_tree_print.py'
    - /bin/sh: 1: ./testty.py: Permission denied
    """

    PATTERNS = {
        "permission_denied": r"Permission denied:\s*['\"]?(?P<file_path>[^'\"]+)['\"]?",
    }

    EXAMPLES = [
        (
            "PermissionError: [Errno 13] Permission denied: './test.py'",
            {
                "clue_type": "permission_denied",
                "confidence": 1.0,
                "context": {"file_path": "./test.py"},
            },
        ),
        (
            "/bin/sh: 1: ./testty.py: Permission denied",
            {
                "clue_type": "permission_denied",
                "confidence": 0.9,
                "context": {"file_path": "./testty.py"},
            },
        ),
    ]

"""
Detectors for permission-related errors.
"""

import re
import typing as T
from pipeline.detectors.base import Detector
from pipeline.models import ErrorClue


class PermissionDeniedDetector(Detector):
    """
    Detect permission denied errors.

    Matches patterns like:
    - PermissionError: [Errno 13] Permission denied: './test_tree_print.py'
    - Permission denied: './test_tree_print.py'
    - /bin/sh: 1: ./testty.py: Permission denied
    """

    PATTERNS = {
        "py_permission_denied": r"Permission denied:\s*['\"]?(?P<file_path>[^'\"]+)['\"]?",
        "sh_permission_denied": r":\s*(?P<file_path>[^:]+):\s*Permission denied",
    }

    EXAMPLES = [
        (
            "PermissionError: [Errno 13] Permission denied: './test.py'",
            {
                "clue_type": "py_permission_denied",
                "confidence": 1.0,
                "context": {"file_path": "./test.py"},
            },
        ),
        (
            "/bin/sh: 1: ./testty.py: Permission denied",
            {
                "clue_type": "sh_permission_denied",
                "confidence": 1.0,
                "context": {"file_path": "./testty.py"},
            },
        ),
    ]

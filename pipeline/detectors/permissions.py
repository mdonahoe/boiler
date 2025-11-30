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
        "permission_denied_colon": r"Permission denied:\s*['\"]?([^'\"]+)['\"]?",
        "permission_denied_sh": r":\s*([^\s:]+):\s*Permission denied",
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

    @property
    def name(self) -> str:
        return "PermissionDeniedDetector"

    def pattern_to_clue(
        self,
        pattern_name: str,
        match: T.Match[str],
        combined: str,
    ) -> T.Optional[ErrorClue]:
        if pattern_name == "permission_denied_colon":
            file_path = match.group(1).strip()
            return ErrorClue(
                clue_type="permission_denied",
                confidence=1.0,
                context={"file_path": file_path},
                source_line=match.group(0),
            )
        elif pattern_name == "permission_denied_sh":
            file_path = match.group(1).strip()
            return ErrorClue(
                clue_type="permission_denied",
                confidence=0.9,
                context={"file_path": file_path},
                source_line=match.group(0),
            )
        return None

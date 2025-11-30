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

    def detect(self, stderr: str, stdout: str = "") -> T.List[ErrorClue]:
        """Override to handle duplicate detection and pattern order"""
        combined = stderr + "\n" + stdout

        # Skip if no permission error keywords
        if "PermissionError:" not in combined and "Permission denied" not in combined:
            return []

        clues = []
        seen_files = set()

        # Pattern 1: Permission denied: './file.py'
        pattern1 = r"Permission denied:\s*['\"]?([^'\"]+)['\"]?"
        for match in re.finditer(pattern1, combined):
            file_path = match.group(1).strip()
            if file_path not in seen_files:
                seen_files.add(file_path)
                clues.append(
                    ErrorClue(
                        clue_type="permission_denied",
                        confidence=1.0,
                        context={"file_path": file_path},
                        source_line=match.group(0),
                    )
                )

        # Pattern 2: /bin/sh format: "path: Permission denied"
        pattern2 = r":\s*([^\s:]+):\s*Permission denied"
        for match in re.finditer(pattern2, combined):
            file_path = match.group(1).strip()
            if file_path not in seen_files:
                seen_files.add(file_path)
                clues.append(
                    ErrorClue(
                        clue_type="permission_denied",
                        confidence=0.9,
                        context={"file_path": file_path},
                        source_line=match.group(0),
                    )
                )

        return clues

    def pattern_to_clue(
        self,
        pattern_name: str,
        match: T.Match[str],
        combined: str,
    ) -> T.Optional[ErrorClue]:
        """Not used - detect() is overridden"""
        return None

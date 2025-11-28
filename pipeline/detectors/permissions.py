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

    @property
    def name(self) -> str:
        return "PermissionDeniedDetector"

    def detect(self, stderr: str, stdout: str = "") -> T.List[ErrorClue]:
        combined = stderr + "\n" + stdout

        # Skip if no permission error keywords
        if "PermissionError:" not in combined and "Permission denied" not in combined:
            return []

        clues = []

        # Pattern 1: PermissionError: [Errno 13] Permission denied: './file.py'
        pattern1 = r"Permission denied:\s*['\"]?([^'\"]+)['\"]?"
        for match in re.finditer(pattern1, combined):
            file_path = match.group(1).strip()
            clues.append(ErrorClue(
                clue_type="permission_denied",
                confidence=1.0,
                context={"file_path": file_path},
                source_line=match.group(0)
            ))

        # Pattern 2: /bin/sh format: "path: Permission denied"
        pattern2 = r":\s*([^\s:]+):\s*Permission denied"
        for match in re.finditer(pattern2, combined):
            file_path = match.group(1).strip()
            # Avoid duplicate if already found by pattern1
            if not any(c.context.get("file_path") == file_path for c in clues):
                clues.append(ErrorClue(
                    clue_type="permission_denied",
                    confidence=0.9,  # Slightly lower confidence for this pattern
                    context={"file_path": file_path},
                    source_line=match.group(0)
                ))

        return clues

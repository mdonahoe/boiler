"""
Detector for C compilation errors for incomplete struct/type errors.
"""

import re
import typing as T
from src.pipeline.detectors.base import Detector
from src.pipeline.models import ErrorClue


class CIncompleteTypeDetector(Detector):
    """
    Detect C compilation errors for incomplete struct/type errors.

    Matches patterns like:
    - error: field 'orig_termios' has incomplete type
    - error: storage size of 'raw' isn't known
    - These usually indicate missing header files for struct definitions
    """

    PATTERNS = {
        # Refactored to avoid multiple lazy quantifiers - uses greedy matching within lines
        "missing_c_include": r"(?P<file_path>[a-zA-Z0-9_./\-]+\.c):\d+:\d+:[^\n]*error:[^\n]*(?:has incomplete type|storage size).*struct\s+(?P<struct_name>termios|winsize|stat|tm|sigaction|dirent)",
    }

    EXAMPLES = [
        (
            "dim.c:81:18: error: field 'orig_termios' has incomplete type\n   81 |   struct termios orig_termios;",
            {
                "clue_type": "missing_c_include",
                "confidence": 1.0,
                "context": {
                    "file_path": "dim.c",
                    "struct_name": "termios",
                },
            },
        ),
    ]

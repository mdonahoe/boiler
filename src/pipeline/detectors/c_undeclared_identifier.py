"""
Detector for C compilation errors for undeclared identifiers.
"""

import re
import typing as T
from src.pipeline.detectors.base import Detector
from src.pipeline.models import ErrorClue


class CUndeclaredIdentifierDetector(Detector):
    """
    Detect C compilation errors for undeclared identifiers with include suggestions.

    Matches patterns like:
    - error: 'NULL' undeclared here (not in a function)
    - note: 'NULL' is defined in header '<stddef.h>'; did you forget to '#include <stddef.h>'?

    Also detects undeclared identifiers without include suggestions (missing functions):
    - error: 'disableRawMode' undeclared (first use in this function)
    """

    PATTERNS = {
        # Refactored to avoid multiple lazy quantifiers - uses greedy matching
        "missing_c_include": r"(?P<file_path>[a-zA-Z0-9_./\-]+\.c):\d+:\d+:[^\n]*undeclared.*note:.*is defined in header\s+['\u2018]<(?P<suggested_include>[^>]+)>['\u2019]",
        "missing_c_function": r"(?P<file_path>[a-zA-Z0-9_./\-]+\.c):(?P<line_number>\d+):\d+:\s+error:\s+['\u2018](?P<identifier>[^'\u2019]+)['\u2019]\s+undeclared\s+\(first use",
    }

    EXAMPLES = [
        (
            "test.c:5:10: error: 'NULL' undeclared\nnote: 'NULL' is defined in header '<stddef.h>'",
            {
                "clue_type": "missing_c_include",
                "confidence": 1.0,
                "context": {
                    "file_path": "test.c",
                    "suggested_include": "stddef.h",
                },
            },
        ),
        (
            "test.c:15:3: error: 'disableRawMode' undeclared (first use in this function)",
            {
                "clue_type": "missing_c_function",
                "confidence": 1.0,
                "context": {
                    "file_path": "test.c",
                    "line_number": "15",
                    "identifier": "disableRawMode",
                },
            },
        ),
    ]

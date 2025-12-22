"""
Detector for C "unknown type name" errors.
"""

import re
import typing as T
from src.pipeline.detectors.base import Detector
from src.pipeline.models import ErrorClue


class CUnknownTypeDetector(Detector):
    """
    Detect C "unknown type name" errors.

    Matches patterns like:
    - error: unknown type name 'TSNode'
    - error: unknown type name 'struct winsize'

    The planner will use git grep to find which header file defines the type.
    """

    PATTERNS = {
        "unknown_type_name": r"(?P<file_path>[a-zA-Z0-9_./\-]+\.c):(?P<line_number>\d+):\d+:\s+error:\s+unknown type name\s+['\u2018](?P<type_name>[^'\u2019]+)['\u2019]",
    }

    EXAMPLES = [
        (
            "dim.c:17:1: error: unknown type name 'TSLanguage'",
            {
                "clue_type": "unknown_type_name",
                "confidence": 1.0,
                "context": {
                    "file_path": "dim.c",
                    "line_number": "17",
                    "type_name": "TSLanguage",
                },
            },
        ),
        (
            "test.c:10:3: error: unknown type name 'struct winsize'",
            {
                "clue_type": "unknown_type_name",
                "confidence": 1.0,
                "context": {
                    "file_path": "test.c",
                    "line_number": "10",
                    "type_name": "struct winsize",
                },
            },
        ),
    ]

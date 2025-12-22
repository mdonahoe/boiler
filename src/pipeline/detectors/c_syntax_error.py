"""
Detector for C/C++ syntax errors in header files.
"""

import re
import typing as T
from src.pipeline.detectors.base import Detector
from src.pipeline.models import ErrorClue


class CSyntaxErrorDetector(Detector):
    """
    Detect C/C++ syntax errors that indicate corrupted source or header files.

    Matches patterns like:
    - tree-sitter/lib/include/tree_sitter/api.h:1336:9: error: expected identifier or '(' before 'void'
    - foo.h:42:1: error: expected ';', identifier or '(' before 'int'
    - bar.h:10:5: error: expected declaration specifiers before 'return'
    - dim.c:2197:3: error: expected identifier or '(' before 'return'
    """

    PATTERNS = {
        "c_syntax_error_in_header": r"(?P<file_path>[^\s:]+\.h):(?P<line_number>\d+):\d+:\s+error:\s+expected\s+.+?\s+before\s+['\u2018](?P<unexpected_token>[^'\u2019']+)['\u2019']",
        "c_syntax_error_in_source": r"(?P<file_path>[^\s:]+\.c):(?P<line_number>\d+):\d+:\s+error:\s+expected\s+.+?\s+before\s+['\u2018](?P<unexpected_token>[^'\u2019']+)['\u2019']",
    }

    EXAMPLES = [
        (
            "tree-sitter/lib/include/tree_sitter/api.h:1336:9: error: expected identifier or '(' before 'void'",
            {
                "clue_type": "c_syntax_error_in_header",
                "confidence": 1.0,
                "context": {
                    "file_path": "tree-sitter/lib/include/tree_sitter/api.h",
                    "line_number": "1336",
                    "unexpected_token": "void",
                },
            },
        ),
        (
            "foo.h:42:1: error: expected ';', identifier or '(' before 'int'",
            {
                "clue_type": "c_syntax_error_in_header",
                "confidence": 1.0,
                "context": {
                    "file_path": "foo.h",
                    "line_number": "42",
                    "unexpected_token": "int",
                },
            },
        ),
        (
            "dim.c:2197:3: error: expected identifier or '(' before 'return'",
            {
                "clue_type": "c_syntax_error_in_source",
                "confidence": 1.0,
                "context": {
                    "file_path": "dim.c",
                    "line_number": "2197",
                    "unexpected_token": "return",
                },
            },
        ),
    ]

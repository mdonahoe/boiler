"""
Detector for C implicit function declaration errors.
"""

import re
import typing as T
from pipeline.detectors.base import Detector
from pipeline.models import ErrorClue


class CImplicitDeclarationDetector(Detector):
    """
    Detect C implicit function declaration errors that suggest missing includes.

    Matches patterns like:
    - error: implicit declaration of function 'printf' [-Werror=implicit-function-declaration]
    - note: include '<stdio.h>' or provide a declaration of 'printf'
    """

    PATTERNS = {
        "missing_c_include": r"(?P<file_path>[a-zA-Z0-9_./\-]+\.c):\d+:\d+:\s+(?:error|warning):\s+implicit declaration of function\s+['\u2018](?P<function_name>[^'\u2019]+)['\u2019].*?note:\s+include\s+['\u2018]<(?P<suggested_include>[^>]+)>['\u2019]",
        "missing_c_function": r"(?P<file_path>[a-zA-Z0-9_./\-]+\.c):(?P<line_number>\d+):\d+:\s+(?:error|warning):\s+implicit declaration of function\s+['\u2018](?P<function_name>[^'\u2019]+)['\u2019]",
    }

    EXAMPLES = [
        (
            "test.c:5:5: error: implicit declaration of function 'printf'\nnote: include '<stdio.h>' or provide a declaration of 'printf'",
            {
                "clue_type": "missing_c_include",
                "confidence": 1.0,
                "context": {
                    "file_path": "test.c",
                    "function_name": "printf",
                    "suggested_include": "stdio.h",
                },
            },
        ),
        (
            "test.c:10:5: error: implicit declaration of function 'myFunction'",
            {
                "clue_type": "missing_c_function",
                "confidence": 1.0,
                "context": {
                    "file_path": "test.c",
                    "line_number": "10",
                    "function_name": "myFunction",
                },
            },
        ),
    ]

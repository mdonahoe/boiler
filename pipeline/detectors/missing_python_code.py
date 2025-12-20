"""
Detector for missing Python code (classes, functions, imports).
"""

import re
import typing as T
from pipeline.detectors.base import Detector
from pipeline.models import ErrorClue


class MissingPythonCodeDetector(Detector):
    """
    Detect when Python files are missing expected code (classes, functions, imports).

    Matches patterns like:
    - AssertionError: 'class TestClass' not found in '...\nexample.py - 13 lines\n...'
    - AssertionError: 'def hello_world' not found in '...'
    - Expected to see 'class ClassName' but got something else
    """

    PATTERNS = {
        "missing_python_code": r"'(?P<missing_element>(?:def|class|import)\s+\w+(?:\s*\(.*\))?)'.*?not found.*?(?:\\n|[\s\n])*?(?P<file_path>[a-zA-Z0-9_-]+\.py)\s+-\s+\d+\s+lines",
    }

    EXAMPLES = [
        (
            "AssertionError: 'class TestClass' not found in 'example.py - 13 lines'",
            {
                "clue_type": "missing_python_code",
                "confidence": 1.0,
                "context": {
                    "file_path": "example.py",
                    "missing_element": "class TestClass",
                },
            },
        ),
        (
            "AssertionError: 'def hello_world' not found in 'test.py - 5 lines'",
            {
                "clue_type": "missing_python_code",
                "confidence": 1.0,
                "context": {
                    "file_path": "test.py",
                    "missing_element": "def hello_world",
                },
            },
        ),
    ]

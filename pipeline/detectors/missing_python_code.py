"""
Detector for missing Python code (classes, functions, imports).

only used by dim unit tests
"""

import re
import typing as T
from pipeline.detectors.base import Detector
from pipeline.models import ErrorClue


class MissingPythonCodeDetector(Detector):
    """
    Detect when Python files are missing expected code (classes, functions, imports).

    Matches patterns like:
    - AssertionError: 'class TestClass' not found in 'anything example.py - 13 lines\n...'
    """

    PATTERNS = {
        "missing_python_code": r"Error: '(?P<missing_element>[^']+)' not found"
    }

    EXAMPLES = [
        (
            "AssertionError: 'class TestClass' not found in 'example.py - 13 lines'",
            {
                "clue_type": "missing_python_code",
                "confidence": 1.0,
                "context": {
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
                    "missing_element": "def hello_world",
                },
            },
        ),
        (
            "AssertionError: 'class Foo' not found in 'nonexistent.py - 3 lines...'",
            {
                "clue_type": "missing_python_code",
                "confidence": 1.0,
                "context": {
                    "missing_element": "class Foo",
                },
            },
        ),
    ]

"""
Detectors for Python code issues (missing classes, functions, etc.).
"""

import re
import typing as T
from pipeline.detectors.base import RegexDetector
from pipeline.models import ErrorClue


class MissingPythonCodeDetector(RegexDetector):
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


class PythonNameErrorDetector(RegexDetector):
    """
    Detect Python NameError exceptions indicating missing imports or code.

    Matches patterns like:
    - NameError: name 'fcntl' is not defined
    - NameError: global name 'SomeClass' is not defined
    """

    PATTERNS = {
        "python_name_error": r'File "(?P<file_path>[^"]+\.py)", line (?P<line_number>\d+),.*?NameError: (?:global )?name \'(?P<undefined_name>\w+)\' is not defined',
    }

    EXAMPLES = [
        (
            'File "test.py", line 5, in test_func\nNameError: name \'fcntl\' is not defined',
            {
                "clue_type": "python_name_error",
                "confidence": 1.0,
                "context": {
                    "file_path": "test.py",
                    "undefined_name": "fcntl",
                    "line_number": "5",
                },
            },
        ),
    ]

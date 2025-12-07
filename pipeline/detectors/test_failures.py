"""
Detectors for test failure errors (unittest, pytest, etc.).
"""

import re
import typing as T
from pipeline.detectors.base import Detector, Detector
from pipeline.models import ErrorClue


class TestFailureDetector(Detector):
    """
    Detect test failures and extract test file paths and suspected filenames.
    
    Matches patterns like:
    - unittest tracebacks with file paths and line numbers
    - AssertionError messages that mention filenames
    - Test failure output that indicates missing files
    """

    PATTERNS = {
        "test_failure": r"File\s+['\"](?P<test_file>[^'\"]+\.py)['\"],\s+line\s+(?P<line_number>\d+),\s+in\s+(?P<test_name>\w+)",
        "test_assertion_with_filename": r"AssertionError:\s*['\"](?P<suspected_file>[^'\"]+\.(?:py|txt|md|c|h|cpp|hpp|json|yaml|yml|sh))['\"].*?not found",
        "c_test_failure": r"(?P<test_file>[^\s:]+\.c):(?P<line_number>\d+):\s*(?P<test_name>\w+):\s*Assertion\s*[`'](?P<assertion>[^'`]+)[`']\s*failed",
        "test_docstring_with_missing_file": r"Test that.*?(?:can open|open).*?(?P<suspected_file>[a-zA-Z0-9_-]+\.(?:c|h|cpp|hpp|py|txt|md|json|yaml|yml|sh|rs|go|java|js|ts)|README\.md).*?fopen:\s*No such file or directory",
    }

    EXAMPLES = [
        (
            "File '/path/to/test_dim.py', line 235, in test_open_readme_and_view_first_line",
            {
                "clue_type": "test_failure",
                "confidence": 1.0,
                "context": {
                    "test_file": "/path/to/test_dim.py",
                    "line_number": "235",
                    "test_name": "test_open_readme_and_view_first_line",
                },
            },
        ),
        (
            "AssertionError: 'hello_world.txt' not found in 'fopen: No such file or directory'",
            {
                "clue_type": "test_assertion_with_filename",
                "confidence": 1.0,
                "context": {
                    "suspected_file": "hello_world.txt",
                },
            },
        ),
        (
            "FAIL: test_open_readme_and_view_first_line (__main__.TestDimFileOperations.test_open_readme_and_view_first_line)\nTest that dim can open README.md and display its first line.\n----------------------------------------------------------------------\nAssertionError: 'dim' not found in 'fopen: No such file or directory' : Expected to see 'dim' (first line of README)",
            {
                "clue_type": "test_docstring_with_missing_file",
                "confidence": 1.0,
                "context": {
                    "suspected_file": "README.md",
                },
            },
        ),
    ]


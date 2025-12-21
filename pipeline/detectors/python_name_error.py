"""
Detector for Python NameError exceptions.
"""

import re
import typing as T
from pipeline.detectors.base import Detector
from pipeline.models import ErrorClue


class PythonNameErrorDetector(Detector):
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

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
        "missing_python_code": r"'((?:def|class|import)\s+\w+(?:\s*\(.*\))?)'.*?not found.*?(?:\\n|[\s\n])*?([a-zA-Z0-9_-]+\.py)\s+-\s+\d+\s+lines",
    }

    EXAMPLES = [
        (
            "AssertionError: 'class TestClass' not found in 'example.py - 13 lines'",
            {
                "clue_type": "missing_python_code",
                "confidence": 1.0,
                "context": {
                    "file_path": "example.py",
                    "element_type": "class",
                    "element_name": "TestClass",
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
                    "element_type": "def",
                    "element_name": "hello_world",
                },
            },
        ),
    ]

    @property
    def name(self) -> str:
        return "MissingPythonCodeDetector"

    def pattern_to_clue(
        self,
        pattern_name: str,
        match: T.Match[str],
        combined: str,
    ) -> T.Optional[ErrorClue]:
        if pattern_name != "missing_python_code":
            return None

        code_element = match.group(1).strip()
        file_path = match.group(2).strip()

        # Extract the name (def foo -> foo, class Bar -> Bar, import baz -> baz)
        name_match = re.search(r"(?:def|class|import)\s+(\w+)", code_element)
        if not name_match:
            return None

        element_name = name_match.group(1)
        return ErrorClue(
            clue_type="missing_python_code",
            confidence=1.0,
            context={
                "file_path": file_path,
                "missing_element": code_element,
                "element_name": element_name,
                "element_type": code_element.split()[0],
            },
            source_line=match.group(0)[:100],
        )


class PythonNameErrorDetector(RegexDetector):
    """
    Detect Python NameError exceptions indicating missing imports or code.

    Matches patterns like:
    - NameError: name 'fcntl' is not defined
    - NameError: global name 'SomeClass' is not defined
    """

    PATTERNS = {
        "python_name_error": r"NameError: (?:global )?name '(\w+)' is not defined",
        "file_reference": r'File "([^"]+\.py)", line (\d+),',
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

    @property
    def name(self) -> str:
        return "PythonNameErrorDetector"

    def pattern_to_clue(
        self,
        pattern_name: str,
        match: T.Match[str],
        combined: str,
    ) -> T.Optional[ErrorClue]:
        if pattern_name != "python_name_error":
            return None

        undefined_name = match.group(1)

        # Parse traceback to find file and undefined name
        file_pattern = r'File "([^"]+\.py)", line (\d+),'

        # Find all file references
        file_matches = list(re.finditer(file_pattern, combined))

        # Find the last file reference before this NameError
        file_path = None
        line_num = None
        for file_match in reversed(file_matches):
            if file_match.start() < match.start():
                file_path = file_match.group(1)
                line_num = file_match.group(2)
                break

        if not file_path:
            return None

        return ErrorClue(
            clue_type="python_name_error",
            confidence=1.0,
            context={
                "file_path": file_path,
                "undefined_name": undefined_name,
                "line_number": line_num,
            },
            source_line=match.group(0),
        )

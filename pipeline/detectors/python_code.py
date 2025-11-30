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

    def detect(self, stderr: str, stdout: str = "") -> T.List[ErrorClue]:
        """Override to handle fallback pattern matching"""
        combined = stderr + "\n" + stdout

        if "AssertionError:" not in combined:
            return []

        clues = []

        # Pattern 1: Direct match with file info
        pattern1 = r"'((?:def|class|import)\s+\w+(?:\s*\(.*\))?)'.*?not found.*?(?:\\n|[\s\n])*?([a-zA-Z0-9_-]+\.py)\s+-\s+\d+\s+lines"
        for match in re.finditer(pattern1, combined, re.DOTALL):
            code_element = match.group(1).strip()
            file_path = match.group(2).strip()

            # Extract the name (def foo -> foo, class Bar -> Bar, import baz -> baz)
            name_match = re.search(r"(?:def|class|import)\s+(\w+)", code_element)
            if name_match:
                element_name = name_match.group(1)
                clues.append(
                    ErrorClue(
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
                )

        # Pattern 2: Fallback - more general match
        if not clues:
            pattern2 = r"'((?:def|class|import)\s+\w+(?:\s*\(.*\))?)'.*?not found"
            for match in re.finditer(pattern2, combined):
                code_element = match.group(1).strip()

                # Try to find the filename nearby
                context_window = combined[
                    max(0, match.start() - 500) : match.end() + 500
                ]
                file_match = re.search(
                    r"(?:\\n|[\s\n])*?([a-zA-Z0-9_-]+\.py)\s+-\s+\d+\s+lines",
                    context_window,
                )

                if file_match:
                    file_path = file_match.group(1)
                    name_match = re.search(
                        r"(?:def|class|import)\s+(\w+)", code_element
                    )
                    if name_match:
                        element_name = name_match.group(1)
                        # Avoid duplicates
                        if not any(
                            c.context.get("element_name") == element_name for c in clues
                        ):
                            clues.append(
                                ErrorClue(
                                    clue_type="missing_python_code",
                                    confidence=0.9,
                                    context={
                                        "file_path": file_path,
                                        "missing_element": code_element,
                                        "element_name": element_name,
                                        "element_type": code_element.split()[0],
                                    },
                                    source_line=match.group(0)[:100],
                                )
                            )

        return clues

    def pattern_to_clue(
        self,
        pattern_name: str,
        match: T.Match[str],
        combined: str,
    ) -> T.Optional[ErrorClue]:
        """Not used - detect() is overridden"""
        return None


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

    def detect(self, stderr: str, stdout: str = "") -> T.List[ErrorClue]:
        """Override to match NameErrors with their file context"""
        combined = stderr + "\n" + stdout

        if "NameError:" not in combined:
            return []

        clues = []

        # Parse traceback to find file and undefined name
        name_error_pattern = r"NameError: (?:global )?name '(\w+)' is not defined"
        file_pattern = r'File "([^"]+\.py)", line (\d+),'

        # Find all file references
        file_matches = list(re.finditer(file_pattern, combined))

        # Find all NameErrors
        for match in re.finditer(name_error_pattern, combined):
            undefined_name = match.group(1)

            # Find the last file reference before this NameError
            file_path = None
            line_num = None
            for file_match in reversed(file_matches):
                if file_match.start() < match.start():
                    file_path = file_match.group(1)
                    line_num = file_match.group(2)
                    break

            if file_path:
                clues.append(
                    ErrorClue(
                        clue_type="python_name_error",
                        confidence=1.0,
                        context={
                            "file_path": file_path,
                            "undefined_name": undefined_name,
                            "line_number": line_num,
                        },
                        source_line=match.group(0),
                    )
                )

        return clues

    def pattern_to_clue(
        self,
        pattern_name: str,
        match: T.Match[str],
        combined: str,
    ) -> T.Optional[ErrorClue]:
        """Not used - detect() is overridden"""
        return None

"""
Detectors for Python code issues (missing classes, functions, etc.).
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

    @property
    def name(self) -> str:
        return "MissingPythonCodeDetector"

    def detect(self, stderr: str, stdout: str = "") -> T.List[ErrorClue]:
        combined = stderr + "\n" + stdout

        if "AssertionError:" not in combined:
            return []

        clues = []

        # Look for patterns indicating missing Python constructs
        # Pattern 1: 'def something' not found in '...filename.py - N lines...'
        # Note: The filename might be preceded by escaped newlines (\\n) or actual whitespace
        pattern1 = r"'((?:def|class|import)\s+\w+(?:\s*\(.*\))?)'.*?not found.*?(?:\\n|[\s\n])*?([a-zA-Z0-9_-]+\.py)\s+-\s+\d+\s+lines"
        for match in re.finditer(pattern1, combined, re.DOTALL):
            code_element = match.group(1).strip()
            file_path = match.group(2).strip()

            # Extract the name (def foo -> foo, class Bar -> Bar, import baz -> baz)
            name_match = re.search(r"(?:def|class|import)\s+(\w+)", code_element)
            if name_match:
                element_name = name_match.group(1)
                clues.append(ErrorClue(
                    clue_type="missing_python_code",
                    confidence=1.0,
                    context={
                        "file_path": file_path,
                        "missing_element": code_element,
                        "element_name": element_name,
                        "element_type": code_element.split()[0]  # 'def', 'class', or 'import'
                    },
                    source_line=match.group(0)[:100]  # Truncate for readability
                ))

        # Pattern 2: 'code element' not found in '...' (more general)
        # This catches cases where the file info might be formatted differently
        if not clues:
            pattern2 = r"'((?:def|class|import)\s+\w+(?:\s*\(.*\))?)'.*?not found"
            for match in re.finditer(pattern2, combined):
                code_element = match.group(1).strip()

                # Try to find the filename nearby
                # Look for .py files mentioned in the surrounding context
                context_window = combined[max(0, match.start() - 500):match.end() + 500]
                file_match = re.search(r'(?:\\n|[\s\n])*?([a-zA-Z0-9_-]+\.py)\s+-\s+\d+\s+lines', context_window)

                if file_match:
                    file_path = file_match.group(1)
                    name_match = re.search(r"(?:def|class|import)\s+(\w+)", code_element)
                    if name_match:
                        element_name = name_match.group(1)
                        # Avoid duplicates
                        if not any(c.context.get("element_name") == element_name for c in clues):
                            clues.append(ErrorClue(
                                clue_type="missing_python_code",
                                confidence=0.9,
                                context={
                                    "file_path": file_path,
                                    "missing_element": code_element,
                                    "element_name": element_name,
                                    "element_type": code_element.split()[0]
                                },
                                source_line=match.group(0)[:100]
                            ))

        return clues


class PythonNameErrorDetector(Detector):
    """
    Detect Python NameError exceptions indicating missing imports or code.

    Matches patterns like:
    - NameError: name 'fcntl' is not defined
    - NameError: global name 'SomeClass' is not defined
    """

    @property
    def name(self) -> str:
        return "PythonNameErrorDetector"

    def detect(self, stderr: str, stdout: str = "") -> T.List[ErrorClue]:
        combined = stderr + "\n" + stdout

        if "NameError:" not in combined:
            return []

        clues = []

        # Parse traceback to find file and undefined name
        # Pattern: NameError: name 'something' is not defined
        # or: NameError: global name 'something' is not defined
        name_error_pattern = r"NameError: (?:global )?name '(\w+)' is not defined"

        # Also look for the file path in the traceback
        # Pattern: File "/path/to/file.py", line 123, in function_name
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
                clues.append(ErrorClue(
                    clue_type="python_name_error",
                    confidence=1.0,
                    context={
                        "file_path": file_path,
                        "undefined_name": undefined_name,
                        "line_number": line_num,
                    },
                    source_line=match.group(0)
                ))

        return clues

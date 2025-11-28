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
        pattern1 = r"'((?:def|class|import)\s+\w+(?:\s*\(.*\))?)'.*?not found.*?([a-zA-Z0-9_-]+\.py)\s+-\s+\d+\s+lines"
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
                file_match = re.search(r'([a-zA-Z0-9_-]+\.py)\s+-\s+\d+\s+lines', context_window)

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

"""
Detectors for test failure errors (unittest, pytest, etc.).
"""

import re
import typing as T
from pipeline.detectors.base import RegexDetector
from pipeline.models import ErrorClue


class TestFailureDetector(RegexDetector):
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
                "confidence": 0.9,
                "context": {
                    "suspected_file": "hello_world.txt",
                },
            },
        ),
    ]

    def detect(self, stderr: str, stdout: str = "") -> T.List[ErrorClue]:
        """
        Detect test failures and extract test file information.
        """
        combined = stderr + "\n" + stdout
        clues = []
        
        # First, find all test failures with file paths
        test_failures = {}
        for match in re.finditer(self.PATTERNS["test_failure"], combined, re.MULTILINE):
            test_file = match.group("test_file")
            line_number = match.group("line_number")
            test_name = match.group("test_name")
            
            # Make path relative if absolute
            if "/" in test_file:
                test_file = test_file.split("/")[-1]  # Just filename for now
            
            key = (test_file, line_number)
            if key not in test_failures:
                test_failures[key] = {
                    "test_file": test_file,
                    "line_number": int(line_number),
                    "test_name": test_name,
                    "suspected_files": [],
                }
        
        # Extract suspected filenames from assertions
        for match in re.finditer(self.PATTERNS["test_assertion_with_filename"], combined, re.MULTILINE):
            suspected_file = match.group("suspected_file")
            # Try to associate with nearest test failure
            # For now, add to all test failures (planner will dedupe)
            for key in test_failures:
                if suspected_file not in test_failures[key]["suspected_files"]:
                    test_failures[key]["suspected_files"].append(suspected_file)
        
        # Create clues for each test failure
        for (test_file, line_number), info in test_failures.items():
            clues.append(ErrorClue(
                clue_type="test_failure",
                confidence=1.0,
                context={
                    "test_file": info["test_file"],
                    "line_number": info["line_number"],
                    "test_name": info["test_name"],
                    "suspected_files": info["suspected_files"],
                },
                source_line=f"Test {info['test_name']} failed at {test_file}:{line_number}"
            ))
        
        return clues

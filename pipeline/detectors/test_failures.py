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
    - git grep test failures showing unwanted content in files
    """

    PATTERNS = {
        "test_failure": r"File\s+['\"](?P<test_file>[^'\"]+\.py)['\"],\s+line\s+(?P<line_number>\d+),\s+in\s+(?P<test_name>\w+)",
        "test_assertion_with_filename": r"AssertionError:\s*['\"](?P<suspected_file>[^'\"]+\.(?:py|txt|md|c|h|cpp|hpp|json|yaml|yml|sh))['\"].*?not found",
        # Capture the git grep failure including the output lines that follow
        "git_grep_test_failure": r"Testing:\s+(?P<test_name>[^.]+)\.\.\.\s+FAIL\s+\((?P<keyword>\w+)\s+found\s+in\s+(?P<search_path>[^)]+)\)(?P<output_section>(?:\s*Found [^:]+:)?(?:\s*[^\n]+:\s*[^\n]+)*)",
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
            "Testing: No wasm references in lib/include... FAIL (wasm found in lib/include/)\n  Found wasm in:\nlib/include/tree_sitter/api.h:typedef struct wasm_engine_t TSWasmEngine;",
            {
                "clue_type": "git_grep_test_failure",
                "confidence": 1.0,
                "context": {
                    "test_name": "No wasm references in lib/include",
                    "keyword": "wasm",
                    "search_path": "lib/include/",
                    "output_section": "\n  Found wasm in:\nlib/include/tree_sitter/api.h:typedef struct wasm_engine_t TSWasmEngine;",
                },
            },
        ),
    ]

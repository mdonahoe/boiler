"""
Detectors for file system errors (missing files, cannot open, etc.).
"""

import re
import typing as T
from pipeline.detectors.base import RegexDetector
from pipeline.models import ErrorClue


class FopenNoSuchFileDetector(RegexDetector):
    """
    Detect fopen errors when a file cannot be opened.

    Matches patterns like:
    - fopen: No such file or directory
    - fopen: example.py: No such file or directory
    - AssertionError: 'example.py' not found in 'fopen: No such file or directory'
    """

    PATTERNS = {
        "fopen_file": r"fopen:\s+([^\s:]+?):\s*No such file or directory",
        "fopen_assertion": r"AssertionError:\s*['\"]([^'\"]+\.py)['\"].*fopen: No such file or directory",
    }

    EXAMPLES = [
        (
            "fopen: example.py: No such file or directory",
            {
                "clue_type": "missing_file",
                "confidence": 1.0,
                "context": {"file_path": "example.py"},
            },
        ),
        (
            "AssertionError: 'hello.py' not found in 'fopen: No such file or directory'",
            {
                "clue_type": "missing_file",
                "confidence": 0.9,
                "context": {"file_path": "hello.py"},
            },
        ),
    ]


class FileNotFoundDetector(RegexDetector):
    """
    Detect FileNotFoundError in various formats.

    Matches patterns like:
    - FileNotFoundError: [Errno 2] No such file or directory: './test.sh'
    - FileNotFoundError: ./test.sh
    """

    PATTERNS = {
        "file_not_found_errno": r"FileNotFoundError:.*?No such file or directory:\s*['\"]([^'\"]+)['\"]",
        "file_not_found_simple": r"FileNotFoundError:\s*([^\s:]+)",
    }

    EXAMPLES = [
        (
            "FileNotFoundError: [Errno 2] No such file or directory: './test.sh'",
            {
                "clue_type": "missing_file",
                "confidence": 1.0,
                "context": {"file_path": "./test.sh"},
            },
        ),
        (
            "FileNotFoundError: ./configure",
            {
                "clue_type": "missing_file",
                "confidence": 0.9,
                "context": {"file_path": "./configure"},
            },
        ),
    ]


class ShellCannotOpenDetector(RegexDetector):
    """
    Detect shell errors when a file cannot be opened.

    Matches patterns like:
    - sh: 0: cannot open makeoptions: No such file
    - /bin/sh: cannot open file: No such file
    """

    PATTERNS = {
        "sh_cannot_open": r"sh:\s*\d+:\s*cannot open\s+([^\s:]+):\s*No such file",
    }

    EXAMPLES = [
        (
            "sh: 0: cannot open makeoptions: No such file",
            {
                "clue_type": "missing_file",
                "confidence": 1.0,
                "context": {"file_path": "makeoptions"},
            },
        ),
    ]


class ShellCommandNotFoundDetector(RegexDetector):
    """
    Detect shell errors when a command/script is not found.

    Matches patterns like:
    - ./test.sh: line 3: ./configure: No such file or directory
    - ./test.sh: 2: ./configure: not found
    - /bin/sh: ./script.sh: not found
    """

    PATTERNS = {
        "shell_line_not_found": r":\s*line\s+\d+:\s*([^\s:]+):\s*No such file or directory",
        "shell_no_colon_not_found": r":\s*\d+:\s*([^\s:]+):\s*not found",
    }

    EXAMPLES = [
        (
            "./test.sh: line 3: ./configure: No such file or directory",
            {
                "clue_type": "missing_file",
                "confidence": 1.0,
                "context": {"file_path": "configure"},
            },
        ),
        (
            "./test.sh: 2: ./script.sh: not found",
            {
                "clue_type": "missing_file",
                "confidence": 0.9,
                "context": {"file_path": "script.sh"},
            },
        ),
    ]


class CatNoSuchFileDetector(RegexDetector):
    """
    Detect cat errors when a file is missing.

    Matches patterns like:
    - cat: Makefile.in: No such file or directory
    """

    PATTERNS = {
        "cat_no_such_file": r"cat:\s*([^\s:]+):\s*No such file or directory",
    }

    EXAMPLES = [
        (
            "cat: Makefile.in: No such file or directory",
            {
                "clue_type": "missing_file",
                "confidence": 1.0,
                "context": {"file_path": "Makefile.in"},
            },
        ),
    ]


class DiffNoSuchFileDetector(RegexDetector):
    """
    Detect diff errors when a file is missing.

    Matches patterns like:
    - diff: test.txt: No such file or directory
    """

    PATTERNS = {
        "diff_no_such_file": r"diff:\s*([^\s:]+):\s*No such file or directory",
    }

    EXAMPLES = [
        (
            "diff: test.txt: No such file or directory",
            {
                "clue_type": "missing_file",
                "confidence": 1.0,
                "context": {"file_path": "test.txt"},
            },
        ),
    ]

    @property
    def name(self) -> str:
        return "DiffNoSuchFileDetector"

    def pattern_to_clue(
        self,
        pattern_name: str,
        match: T.Match[str],
        combined: str,
    ) -> T.Optional[ErrorClue]:
        if pattern_name != "diff_no_such_file":
            return None

        file_path = match.group(1).strip()
        return ErrorClue(
            clue_type="missing_file",
            confidence=1.0,
            context={"file_path": file_path},
            source_line=match.group(0),
        )


class CLinkerErrorDetector(RegexDetector):
    """
    Detect C/C++ linker errors when object files or libraries are missing.

    Matches patterns like:
    - /usr/bin/ld: /tmp/cckoAdDP.o: in function `print_node_text':
    - tree_print.c:(.text+0x137): undefined reference to `ts_node_start_byte'
    - /usr/bin/ld: cannot find -lsomelibrary: No such file or directory
    """

    PATTERNS = {
        "linker_undefined_symbols": r"undefined reference to [`']([^'`]+)[`']",
        "linker_missing_object": r"cannot find\s+([^\s:]+\.o):\s+No such file or directory",
        "linker_missing_library": r"cannot find\s+([^\s:]+):\s+No such file or directory",
    }

    EXAMPLES = [
        (
            "undefined reference to `ts_parser_new'",
            {
                "clue_type": "linker_undefined_symbols",
                "confidence": 1.0,
                "context": {"symbols": ["ts_parser_new"]},
            },
        ),
        (
            "/usr/bin/ld: cannot find exrecover.o: No such file or directory",
            {
                "clue_type": "missing_object_file",
                "confidence": 1.0,
                "context": {"object_file": "exrecover.o"},
            },
        ),
    ]


class CCompilationErrorDetector(RegexDetector):
    """
    Detect C/C++ compilation errors when header files are missing.

    Matches patterns like:
    - /tmp/ex_bar.c:82:10: fatal error: ex.h: No such file or directory
    -    82 | #include "ex.h"
    - lib/src/node.c:2:10: fatal error: ./point.h: No such file or directory
    """

    PATTERNS = {
        "c_fatal_error": r"fatal error:\s+([^\s:]+):\s+No such file or directory",
    }

    EXAMPLES = [
        (
            "/tmp/ex_bar.c:82:10: fatal error: ex.h: No such file or directory",
            {
                "clue_type": "missing_file",
                "confidence": 1.0,
                "context": {
                    "file_path": "ex.h",
                },
            },
        ),
    ]


class CIncompleteTypeDetector(RegexDetector):
    """
    Detect C compilation errors for incomplete struct/type errors.

    Matches patterns like:
    - error: field 'orig_termios' has incomplete type
    - error: storage size of 'raw' isn't known
    - These usually indicate missing header files for struct definitions
    """

    PATTERNS = {
        "c_incomplete_type": r"error:.*has incomplete type",
        "c_incomplete_storage": r"storage size",
    }

    EXAMPLES = [
        (
            "struct termios raw;\ntest.c:10: error: field 'orig_termios' has incomplete type",
            {
                "clue_type": "missing_c_include",
                "confidence": 1.0,
                "context": {
                    "struct_name": "termios",
                },
            },
        ),
    ]

    @property
    def name(self) -> str:
        return "CIncompleteTypeDetector"

    def pattern_to_clue(
        self,
        pattern_name: str,
        match: T.Match[str],
        combined: str,
    ) -> T.Optional[ErrorClue]:
        if pattern_name != "c_incomplete_type":
            return None

        # Map of common struct names to their headers
        type_to_header = {
            "termios": "termios.h",
            "winsize": "sys/ioctl.h",
            "stat": "sys/stat.h",
            "tm": "time.h",
            "sigaction": "signal.h",
            "dirent": "dirent.h",
        }

        # Pattern to extract struct name
        struct_pattern = r"struct\s+([a-zA-Z_][a-zA-Z0-9_]*)"

        # Look for struct names around this match
        error_context = combined[
            max(0, match.start() - 200) : match.end() + 100
        ]

        # Find the most recent struct declaration in context
        struct_matches = list(re.finditer(struct_pattern, error_context))
        if not struct_matches:
            return None

        struct_name = struct_matches[-1].group(1)

        # Check if we know which header this struct needs
        if struct_name not in type_to_header:
            return None

        header = type_to_header[struct_name]

        # Try to find the source file
        file_pattern = r"^([a-zA-Z0-9_./\-]+\.c):(\d+):"
        file_matches = list(
            re.finditer(
                file_pattern, combined[: match.start()], re.MULTILINE
            )
        )

        source_file = "unknown"
        line_number = 0
        if file_matches:
            last_match = file_matches[-1]
            source_file = last_match.group(1).strip()
            line_number = int(last_match.group(2))

        return ErrorClue(
            clue_type="missing_c_include",
            confidence=0.9,
            context={
                "file_path": source_file,
                "line_number": line_number,
                "struct_name": struct_name,
                "suggested_include": header,
            },
            source_line=match.group(0),
        )


class CImplicitDeclarationDetector(RegexDetector):
    """
    Detect C implicit function declaration errors that suggest missing includes.

    Matches patterns like:
    - error: implicit declaration of function 'printf' [-Werror=implicit-function-declaration]
    - note: include '<stdio.h>' or provide a declaration of 'printf'
    """

    PATTERNS = {
        "missing_c_include": r"implicit declaration of function\s+['\u2018](?P<function_name>[^'\u2019]+)['\u2019].*?note:\s+include\s+['\u2018]<(?P<suggested_include>[^>]+)>['\u2019]",
        "missing_c_function": r"(?P<file_path>[a-zA-Z0-9_./\-]+\.c):(?P<line_number>\d+):\d+:\s+(?:error|warning):\s+implicit declaration of function\s+['\u2018](?P<function_name>[^'\u2019]+)['\u2019]",
    }

    EXAMPLES = [
        (
            "test.c:5:5: error: implicit declaration of function 'printf'\nnote: include '<stdio.h>' or provide a declaration of 'printf'",
            {
                "clue_type": "missing_c_include",
                "confidence": 1.0,
                "context": {
                    "function_name": "printf",
                    "suggested_include": "stdio.h",
                },
            },
        ),
    ]


class CUndeclaredIdentifierDetector(RegexDetector):
    """
    Detect C compilation errors for undeclared identifiers with include suggestions.

    Matches patterns like:
    - error: 'NULL' undeclared here (not in a function)
    - note: 'NULL' is defined in header '<stddef.h>'; did you forget to '#include <stddef.h>'?

    Also detects undeclared identifiers without include suggestions (missing functions):
    - error: 'disableRawMode' undeclared (first use in this function)
    """

    PATTERNS = {
        "missing_c_include": r"undeclared.*?note:.*is defined in header\s+['\u2018]<(?P<suggested_include>[^>]+)>['\u2019]",
        "missing_c_function": r"(?P<file_path>[a-zA-Z0-9_./\-]+\.c):(?P<line_number>\d+):\d+:\s+error:\s+['\u2018](?P<identifier>[^'\u2019]+)['\u2019]\s+undeclared\s+\(first use",
    }

    EXAMPLES = [
        (
            "test.c:5: error: 'NULL' undeclared\nnote: 'NULL' is defined in header '<stddef.h>'",
            {
                "clue_type": "missing_c_include",
                "confidence": 1.0,
                "context": {
                    "suggested_include": "stddef.h",
                },
            },
        ),
    ]

"""
Detectors for file system errors (missing files, cannot open, etc.).
"""

import re
import typing as T
from pipeline.detectors.base import Detector
from pipeline.models import ErrorClue


class FopenNoSuchFileDetector(Detector):
    """
    Detect fopen errors when a file cannot be opened.

    Matches patterns like:
    - fopen: No such file or directory
    - fopen: example.py: No such file or directory
    - AssertionError: 'example.py' not found in 'fopen: No such file or directory'
    """

    PATTERNS = {
        "missing_file": r"fopen:\s+(?P<file_path>[^\s:]+?):\s*No such file or directory",
        "missing_file_assertion": r"AssertionError:\s*['\"](?P<file_path>[^'\"]+\.(?:py|txt|md|c|h|cpp|hpp|json|yaml|yml|sh|rs|go|java|js|ts|html|css|xml|sql))['\"].*fopen:\s*No such file or directory",
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
                "clue_type": "missing_file_assertion",
                "confidence": 1.0,
                "context": {"file_path": "hello.py"},
            },
        ),
    ]


class FileNotFoundDetector(Detector):
    """
    Detect FileNotFoundError in various formats.

    Matches patterns like:
    - FileNotFoundError: [Errno 2] No such file or directory: './test.sh'
    - FileNotFoundError: ./test.sh
    """

    PATTERNS = {
        "missing_file": r"FileNotFoundError:.*?No such file or directory:\s*['\"](?P<file_path>[^'\"]+)['\"]",
        "missing_file_simple": r"FileNotFoundError:\s*(?P<file_path>[^\s:]+)",
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
                "clue_type": "missing_file_simple",
                "confidence": 1.0,
                "context": {"file_path": "./configure"},
            },
        ),
    ]


class ShellCannotOpenDetector(Detector):
    """
    Detect shell errors when a file cannot be opened.

    Matches patterns like:
    - sh: 0: cannot open makeoptions: No such file
    - /bin/sh: cannot open file: No such file
    """

    PATTERNS = {
        "missing_file": r"sh:\s*\d+:\s*cannot open\s+(?P<file_path>[^\s:]+):\s*No such file",
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


class CannotOpenFileDetector(Detector):
    """
    Detect generic "Cannot open file" errors from programs.

    Matches patterns like:
    - Error: Cannot open file 'example.c'
    - Error: Cannot open file "example.py"
    - error: Cannot open file 'test.txt'
    """

    PATTERNS = {
        "missing_file": r"[Ee]rror:?\s+Cannot open file\s+['\"](?P<file_path>[^'\"]+)['\"]",
    }

    EXAMPLES = [
        (
            "Error: Cannot open file 'example.c'",
            {
                "clue_type": "missing_file",
                "confidence": 1.0,
                "context": {"file_path": "example.c"},
            },
        ),
        (
            "error: Cannot open file \"example.py\"",
            {
                "clue_type": "missing_file",
                "confidence": 1.0,
                "context": {"file_path": "example.py"},
            },
        ),
    ]


class ShellCommandNotFoundDetector(Detector):
    """
    Detect shell errors when a command/script is not found.

    Matches patterns like:
    - ./test.sh: line 3: ./configure: No such file or directory
    - ./test.sh: 2: ./configure: not found
    - /bin/sh: ./script.sh: not found
    """

    PATTERNS = {
        "missing_file": r":\s*line\s+\d+:\s*\.?/?(?P<file_path>[^\s:]+):\s*No such file or directory",
        "missing_file_not_found": r":\s*\d+:\s*\.?/?(?P<file_path>[^\s:]+):\s*not found",
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
                "clue_type": "missing_file_not_found",
                "confidence": 1.0,
                "context": {"file_path": "script.sh"},
            },
        ),
    ]


class CatNoSuchFileDetector(Detector):
    """
    Detect cat errors when a file is missing.

    Matches patterns like:
    - cat: Makefile.in: No such file or directory
    """

    PATTERNS = {
        "missing_file": r"cat:\s*(?P<file_path>[^\s:]+):\s*No such file or directory",
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


class DiffNoSuchFileDetector(Detector):
    """
    Detect diff errors when a file is missing.

    Matches patterns like:
    - diff: test.txt: No such file or directory
    """

    PATTERNS = {
        "missing_file": r"diff:\s*(?P<file_path>[^\s:]+):\s*No such file or directory",
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


class CLinkerErrorDetector(Detector):
    """
    Detect C/C++ linker undefined symbol errors and missing files.

    Matches patterns like:
    - tree_print.c:(.text+0x137): undefined reference to `ts_node_start_byte'
    - /usr/bin/ld: cannot find exrecover.o: No such file or directory
    """

    PATTERNS = {
        "linker_undefined_symbols": r"undefined reference to [`'](?P<symbol>[^'`]+)[`']",
        "missing_file": r"/usr/bin/ld:.*?cannot find\s+(?P<file_path>[^\s:]+):\s+No such file or directory",
    }

    EXAMPLES = [
        (
            "undefined reference to `ts_parser_new'",
            {
                "clue_type": "linker_undefined_symbols",
                "confidence": 1.0,
                "context": {"symbol": "ts_parser_new"},
            },
        ),
        (
            "/usr/bin/ld: cannot find exrecover.o: No such file or directory",
            {
                "clue_type": "missing_file",
                "confidence": 1.0,
                "context": {"file_path": "exrecover.o"},
            },
        ),
    ]


class CCompilationErrorDetector(Detector):
    """
    Detect C/C++ compilation errors when header files are missing.

    Matches patterns like:
    - /tmp/ex_bar.c:82:10: fatal error: ex.h: No such file or directory
    -    82 | #include "ex.h"
    - lib/src/node.c:2:10: fatal error: ./point.h: No such file or directory
    """

    PATTERNS = {
        "missing_file": r"fatal error:\s+\.?/?(?P<file_path>[^\s:]+):\s+No such file or directory",
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


class CIncompleteTypeDetector(Detector):
    """
    Detect C compilation errors for incomplete struct/type errors.

    Matches patterns like:
    - error: field 'orig_termios' has incomplete type
    - error: storage size of 'raw' isn't known
    - These usually indicate missing header files for struct definitions
    """

    PATTERNS = {
        "missing_c_include": r"(?P<file_path>[a-zA-Z0-9_./\-]+\.c):\d+:\d+:.*?error:.*?(?:has incomplete type|storage size).*?struct\s+(?P<struct_name>termios|winsize|stat|tm|sigaction|dirent)",
    }

    EXAMPLES = [
        (
            "dim.c:81:18: error: field 'orig_termios' has incomplete type\n   81 |   struct termios orig_termios;",
            {
                "clue_type": "missing_c_include",
                "confidence": 1.0,
                "context": {
                    "file_path": "dim.c",
                    "struct_name": "termios",
                },
            },
        ),
    ]


class CImplicitDeclarationDetector(Detector):
    """
    Detect C implicit function declaration errors that suggest missing includes.

    Matches patterns like:
    - error: implicit declaration of function 'printf' [-Werror=implicit-function-declaration]
    - note: include '<stdio.h>' or provide a declaration of 'printf'
    """

    PATTERNS = {
        "missing_c_include": r"(?P<file_path>[a-zA-Z0-9_./\-]+\.c):\d+:\d+:\s+(?:error|warning):\s+implicit declaration of function\s+['\u2018](?P<function_name>[^'\u2019]+)['\u2019].*?note:\s+include\s+['\u2018]<(?P<suggested_include>[^>]+)>['\u2019]",
        "missing_c_function": r"(?P<file_path>[a-zA-Z0-9_./\-]+\.c):(?P<line_number>\d+):\d+:\s+(?:error|warning):\s+implicit declaration of function\s+['\u2018](?P<function_name>[^'\u2019]+)['\u2019]",
    }

    EXAMPLES = [
        (
            "test.c:5:5: error: implicit declaration of function 'printf'\nnote: include '<stdio.h>' or provide a declaration of 'printf'",
            {
                "clue_type": "missing_c_include",
                "confidence": 1.0,
                "context": {
                    "file_path": "test.c",
                    "function_name": "printf",
                    "suggested_include": "stdio.h",
                },
            },
        ),
    ]


class CUndeclaredIdentifierDetector(Detector):
    """
    Detect C compilation errors for undeclared identifiers with include suggestions.

    Matches patterns like:
    - error: 'NULL' undeclared here (not in a function)
    - note: 'NULL' is defined in header '<stddef.h>'; did you forget to '#include <stddef.h>'?

    Also detects undeclared identifiers without include suggestions (missing functions):
    - error: 'disableRawMode' undeclared (first use in this function)
    """

    PATTERNS = {
        "missing_c_include": r"(?P<file_path>[a-zA-Z0-9_./\-]+\.c):\d+:\d+:.*?undeclared.*?note:.*is defined in header\s+['\u2018]<(?P<suggested_include>[^>]+)>['\u2019]",
        "missing_c_function": r"(?P<file_path>[a-zA-Z0-9_./\-]+\.c):(?P<line_number>\d+):\d+:\s+error:\s+['\u2018](?P<identifier>[^'\u2019]+)['\u2019]\s+undeclared\s+\(first use",
    }

    EXAMPLES = [
        (
            "test.c:5:10: error: 'NULL' undeclared\nnote: 'NULL' is defined in header '<stddef.h>'",
            {
                "clue_type": "missing_c_include",
                "confidence": 1.0,
                "context": {
                    "file_path": "test.c",
                    "suggested_include": "stddef.h",
                },
            },
        ),
    ]


class CUnknownTypeNameDetector(Detector):
    """
    Detect C compilation errors for unknown type names.

    Matches patterns like:
    - error: unknown type name 'FILE'
    - note: 'FILE' is defined in header '<stdio.h>'; did you forget to '#include <stdio.h>'?
    - error: unknown type name 'state_t'

    This handles types/typedefs that are not recognized, which typically means:
    1. A missing header include (if compiler suggests one)
    2. A missing local header that defines the type
    """

    PATTERNS = {
        # Match "unknown type name" with compiler suggestion for header
        "missing_c_include": r"(?P<file_path>[a-zA-Z0-9_./\-]+\.c):\d+:\d+:.*?unknown type name\s+['\u2018](?P<type_name>[^'\u2019]+)['\u2019].*?note:.*is defined in header\s+['\u2018]<(?P<suggested_include>[^>]+)>['\u2019]",
        # Match "unknown type name" without suggestion (likely needs local header or typedef)
        "missing_c_type": r"(?P<file_path>[a-zA-Z0-9_./\-]+\.c):(?P<line_number>\d+):\d+:\s+error:\s+unknown type name\s+['\u2018]?(?P<type_name>[a-zA-Z0-9_]+)['\u2019]?",
    }

    EXAMPLES = [
        (
            "dim.c:185:3: error: unknown type name 'FILE'\nnote: 'FILE' is defined in header '<stdio.h>'; did you forget to '#include <stdio.h>'?",
            {
                "clue_type": "missing_c_include",
                "confidence": 1.0,
                "context": {
                    "file_path": "dim.c",
                    "type_name": "FILE",
                    "suggested_include": "stdio.h",
                },
            },
        ),
        (
            "src/listeners.c:3:21: error: unknown type name 'state_t'",
            {
                "clue_type": "missing_c_type",
                "confidence": 1.0,
                "context": {
                    "file_path": "src/listeners.c",
                    "line_number": "3",
                    "type_name": "state_t",
                },
            },
        ),
    ]

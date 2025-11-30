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
                "confidence": 0.95,
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

    @property
    def name(self) -> str:
        return "FopenNoSuchFileDetector"

    def detect(self, stderr: str, stdout: str = "") -> T.List[ErrorClue]:
        """Override to handle fallback pattern matching"""
        combined = stderr + "\n" + stdout

        if "fopen:" not in combined and "fopen: No such file or directory" not in combined:
            return []

        clues = []
        seen_files = set()

        # Pattern 1: fopen: filename: No such file or directory
        pattern1 = r"fopen:\s+([^\s:]+?):\s*No such file or directory"
        for match in re.finditer(pattern1, combined):
            file_path = match.group(1).strip()
            if file_path not in seen_files:
                seen_files.add(file_path)
                clues.append(
                    ErrorClue(
                        clue_type="missing_file",
                        confidence=0.95,
                        context={"file_path": file_path},
                        source_line=match.group(0),
                    )
                )

        # Pattern 2: AssertionError mentioning a file that fopen can't open
        if "fopen: No such file or directory" in combined:
            assertion_pattern = r"AssertionError:\s*['\"]([^'\"]+\.py)['\"].*fopen: No such file or directory"
            for match in re.finditer(assertion_pattern, combined):
                file_path = match.group(1).strip()
                if file_path not in seen_files:
                    seen_files.add(file_path)
                    clues.append(
                        ErrorClue(
                            clue_type="missing_file",
                            confidence=0.9,
                            context={"file_path": file_path},
                            source_line=f"fopen: No such file or directory (file: {file_path})",
                        )
                    )

        # Pattern 3: Fallback - look for any file with extension mentioned in context
        if not clues and "fopen: No such file or directory" in combined:
            file_pattern = (
                r"\b([a-zA-Z0-9_-]+\.(?:txt|md|py|c|h|cpp|cc|java|js|html|css))\b"
            )
            matches = list(re.finditer(file_pattern, combined))

            for match in matches:
                file_path = match.group(1).strip()
                if file_path not in seen_files:
                    seen_files.add(file_path)
                    clues.append(
                        ErrorClue(
                            clue_type="missing_file",
                            confidence=0.6,
                            context={"file_path": file_path},
                            source_line="fopen: No such file or directory (inferred from context)",
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

    @property
    def name(self) -> str:
        return "FileNotFoundDetector"

    def pattern_to_clue(
        self,
        pattern_name: str,
        match: T.Match[str],
        combined: str,
    ) -> T.Optional[ErrorClue]:
        if pattern_name == "file_not_found_errno":
            file_path = match.group(1).strip()
            return ErrorClue(
                clue_type="missing_file",
                confidence=1.0,
                context={"file_path": file_path},
                source_line=match.group(0),
            )
        elif pattern_name == "file_not_found_simple":
            file_path = match.group(1).strip()
            return ErrorClue(
                clue_type="missing_file",
                confidence=0.9,
                context={"file_path": file_path},
                source_line=match.group(0),
            )
        return None


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

    @property
    def name(self) -> str:
        return "ShellCannotOpenDetector"

    def pattern_to_clue(
        self,
        pattern_name: str,
        match: T.Match[str],
        combined: str,
    ) -> T.Optional[ErrorClue]:
        if pattern_name != "sh_cannot_open":
            return None

        file_path = match.group(1).strip()
        return ErrorClue(
            clue_type="missing_file",
            confidence=1.0,
            context={"file_path": file_path},
            source_line=match.group(0),
        )


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

    @property
    def name(self) -> str:
        return "ShellCommandNotFoundDetector"

    def pattern_to_clue(
        self,
        pattern_name: str,
        match: T.Match[str],
        combined: str,
    ) -> T.Optional[ErrorClue]:
        if pattern_name == "shell_line_not_found":
            file_path = match.group(1).strip()
            if file_path.startswith("./"):
                file_path = file_path[2:]
            return ErrorClue(
                clue_type="missing_file",
                confidence=1.0,
                context={"file_path": file_path},
                source_line=match.group(0),
            )
        elif pattern_name == "shell_no_colon_not_found":
            file_path = match.group(1).strip()
            if file_path.startswith("./"):
                file_path = file_path[2:]
            return ErrorClue(
                clue_type="missing_file",
                confidence=0.9,
                context={"file_path": file_path},
                source_line=match.group(0),
            )
        return None


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

    @property
    def name(self) -> str:
        return "CatNoSuchFileDetector"

    def pattern_to_clue(
        self,
        pattern_name: str,
        match: T.Match[str],
        combined: str,
    ) -> T.Optional[ErrorClue]:
        if pattern_name != "cat_no_such_file":
            return None

        file_path = match.group(1).strip()
        return ErrorClue(
            clue_type="missing_file",
            confidence=1.0,
            context={"file_path": file_path},
            source_line=match.group(0),
        )


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

    @property
    def name(self) -> str:
        return "CLinkerErrorDetector"

    def pattern_to_clue(
        self,
        pattern_name: str,
        match: T.Match[str],
        combined: str,
    ) -> T.Optional[ErrorClue]:
        if pattern_name == "linker_undefined_symbols":
            # Only process on the first match to avoid duplicates
            # Check if this is the first undefined reference in combined
            first_undefined_pos = combined.find("undefined reference to")
            if match.start() == first_undefined_pos:
                # Collect all undefined symbols in one clue
                undefined_symbols = set()
                pattern = r"undefined reference to [`']([^'`]+)[`']"
                for m in re.finditer(pattern, combined):
                    undefined_symbols.add(m.group(1))

                if undefined_symbols:
                    return ErrorClue(
                        clue_type="linker_undefined_symbols",
                        confidence=1.0,
                        context={"symbols": list(undefined_symbols)},
                        source_line=f"Found {len(undefined_symbols)} undefined references",
                    )
            return None
        elif pattern_name == "linker_missing_object":
            obj_file = match.group(1).strip()
            return ErrorClue(
                clue_type="missing_object_file",
                confidence=1.0,
                context={"object_file": obj_file},
                source_line=match.group(0),
            )
        elif pattern_name == "linker_missing_library":
            library = match.group(1).strip()
            # Skip if this is an object file (they're handled by linker_missing_object)
            if not library.endswith(".o"):
                return ErrorClue(
                    clue_type="missing_library",
                    confidence=1.0,
                    context={"library": library},
                    source_line=match.group(0),
                )
            return None
        return None


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
                    "is_header": True,
                },
            },
        ),
    ]

    @property
    def name(self) -> str:
        return "CCompilationErrorDetector"

    def pattern_to_clue(
        self,
        pattern_name: str,
        match: T.Match[str],
        combined: str,
    ) -> T.Optional[ErrorClue]:
        if pattern_name != "c_fatal_error":
            return None

        file_path = match.group(1).strip()
        # Remove ./ prefix if present
        if file_path.startswith("./"):
            file_path = file_path[2:]

        context = {
            "file_path": file_path,
            "is_header": file_path.endswith(".h"),
        }

        # Try to find the source file being compiled for better context
        source_file_pattern = (
            r"(?:cc|gcc|clang|g\+\+|c\+\+)\s+[^:]*?\s+([^\s]+\.c+)\s+"
        )
        source_match = re.search(source_file_pattern, combined)
        if source_match:
            source_file = source_match.group(1).strip()
            context["source_file"] = source_file
            # Extract the directory of the source file
            import os
            source_dir = os.path.dirname(source_file)
            if source_dir:
                context["source_dir"] = source_dir

        return ErrorClue(
            clue_type="missing_file",
            confidence=1.0,
            context=context,
            source_line=match.group(0),
        )


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
                "confidence": 0.9,
                "context": {
                    "file_path": "test.c",
                    "line_number": 10,
                    "struct_name": "termios",
                    "suggested_include": "termios.h",
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
        "c_implicit_declaration": r"implicit declaration of function",
        "c_implicit_include_suggestion": r"note:\s+include\s+['\u2018]<([^>]+)>['\u2019]",
    }

    EXAMPLES = [
        (
            "test.c:5:5: error: implicit declaration of function 'printf'\nnote: include '<stdio.h>' or provide a declaration of 'printf'",
            {
                "clue_type": "missing_c_include",
                "confidence": 1.0,
                "context": {
                    "file_path": "test.c",
                    "line_number": 5,
                    "function_name": "printf",
                    "suggested_include": "stdio.h",
                },
            },
        ),
    ]

    @property
    def name(self) -> str:
        return "CImplicitDeclarationDetector"

    def pattern_to_clue(
        self,
        pattern_name: str,
        match: T.Match[str],
        combined: str,
    ) -> T.Optional[ErrorClue]:
        if pattern_name != "c_implicit_declaration":
            return None

        # Map stdlib functions to their headers
        stdlib_to_header = {
            "printf": "stdio.h", "fprintf": "stdio.h", "sprintf": "stdio.h",
            "scanf": "stdio.h", "fscanf": "stdio.h", "fopen": "stdio.h",
            "fclose": "stdio.h", "fread": "stdio.h", "fwrite": "stdio.h",
            "fgets": "stdio.h", "fputs": "stdio.h", "getchar": "stdio.h",
            "putchar": "stdio.h", "puts": "stdio.h", "gets": "stdio.h",
            "sscanf": "stdio.h", "snprintf": "stdio.h", "perror": "stdio.h",
            "malloc": "stdlib.h", "calloc": "stdlib.h", "realloc": "stdlib.h",
            "free": "stdlib.h", "atoi": "stdlib.h", "atol": "stdlib.h",
            "strtol": "stdlib.h", "rand": "stdlib.h", "srand": "stdlib.h",
            "exit": "stdlib.h", "abort": "stdlib.h", "atexit": "stdlib.h",
            "strlen": "string.h", "strcpy": "string.h", "strncpy": "string.h",
            "strcat": "string.h", "strncat": "string.h", "strcmp": "string.h",
            "strncmp": "string.h", "strchr": "string.h", "strstr": "string.h",
            "memcpy": "string.h", "memmove": "string.h", "memset": "string.h",
            "memcmp": "string.h", "read": "unistd.h", "write": "unistd.h",
            "open": "unistd.h", "close": "unistd.h", "lseek": "unistd.h",
            "fork": "unistd.h", "sleep": "unistd.h", "usleep": "unistd.h",
            "fcntl": "fcntl.h", "dup": "fcntl.h", "dup2": "fcntl.h",
            "signal": "signal.h", "kill": "signal.h", "raise": "signal.h",
            "pause": "signal.h", "stat": "sys/stat.h", "fstat": "sys/stat.h",
            "lstat": "sys/stat.h", "chmod": "sys/stat.h", "mkdir": "sys/stat.h",
            "time": "time.h", "localtime": "time.h", "gmtime": "time.h",
            "strftime": "time.h", "clock": "time.h", "va_start": "stdarg.h",
            "va_end": "stdarg.h", "va_arg": "stdarg.h", "va_copy": "stdarg.h",
            "sin": "math.h", "cos": "math.h", "tan": "math.h", "sqrt": "math.h",
            "pow": "math.h", "abs": "math.h", "fabs": "math.h",
            "isalpha": "ctype.h", "isdigit": "ctype.h", "isspace": "ctype.h",
            "tolower": "ctype.h", "toupper": "ctype.h",
            "tcgetattr": "termios.h", "tcsetattr": "termios.h",
            "ioctl": "sys/ioctl.h",
        }

        # Find the start of the line containing this match
        line_start = combined.rfind('\n', 0, match.start()) + 1
        line_end = combined.find('\n', match.start())
        if line_end == -1:
            line_end = len(combined)
        
        error_line = combined[line_start:line_end]

        # Extract the implicit declaration information from this line
        implicit_pattern = r"^([a-zA-Z0-9_./\-]+\.c):(\d+):\d+:\s+(?:error|warning):\s+implicit declaration of function ['\u2018]([^'\u2019]+)['\u2019]"
        implicit_match = re.match(implicit_pattern, error_line)
        
        if not implicit_match:
            return None

        source_file = implicit_match.group(1).strip()
        line_number = int(implicit_match.group(2))
        function_name = implicit_match.group(3).strip()

        # Try to find the corresponding include suggestion near this match
        include_pattern1 = r"note:\s+include\s+['\u2018]<([^>]+)>['\u2019]\s+or provide a declaration"
        include_pattern2 = r"note:\s+['\u2018]([^'\u2019]+)['\u2019]\s+is defined in header\s+['\u2018]<([^>]+)>['\u2019]"

        include_name = None
        match_end = match.start() + 200
        
        for inc_match in re.finditer(include_pattern1, combined[match.start(): match_end]):
            include_name = inc_match.group(1).strip()
            break

        if not include_name:
            for inc_match in re.finditer(include_pattern2, combined[match.start(): match_end]):
                if inc_match.group(1) == function_name:
                    include_name = inc_match.group(2).strip()
                    break

        context = {
            "file_path": source_file,
            "line_number": line_number,
            "function_name": function_name,
        }

        # If there's a suggested include, it's a missing include problem
        if include_name:
            context["suggested_include"] = include_name
            return ErrorClue(
                clue_type="missing_c_include",
                confidence=1.0,
                context=context,
                source_line=error_line,
            )
        # Check if it's a known stdlib function
        elif function_name in stdlib_to_header:
            context["suggested_include"] = stdlib_to_header[function_name]
            return ErrorClue(
                clue_type="missing_c_include",
                confidence=0.95,
                context=context,
                source_line=error_line,
            )
        else:
            # No include suggestion and not a stdlib function
            return ErrorClue(
                clue_type="missing_c_function",
                confidence=0.8,
                context={
                    "file_path": source_file,
                    "line_number": line_number,
                    "symbols": [function_name],
                },
                source_line=error_line,
            )


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
        "c_undeclared": r"undeclared",
        "c_unknown_type": r"unknown type name",
    }

    EXAMPLES = [
        (
            "test.c:5: error: 'NULL' undeclared\nnote: 'NULL' is defined in header '<stddef.h>'",
            {
                "clue_type": "missing_c_include",
                "confidence": 1.0,
                "context": {
                    "file_path": "test.c",
                    "line_number": 5,
                    "suggested_include": "stddef.h",
                },
            },
        ),
    ]

    @property
    def name(self) -> str:
        return "CUndeclaredIdentifierDetector"

    def pattern_to_clue(
        self,
        pattern_name: str,
        match: T.Match[str],
        combined: str,
    ) -> T.Optional[ErrorClue]:
        if pattern_name not in ("c_undeclared", "c_unknown_type"):
            return None

        # Map stdlib constants/macros to their headers
        stdlib_to_header = {
            "O_RDWR": "fcntl.h", "O_RDONLY": "fcntl.h", "O_WRONLY": "fcntl.h",
            "O_CREAT": "fcntl.h", "O_APPEND": "fcntl.h", "O_EXCL": "fcntl.h",
            "O_TRUNC": "fcntl.h", "O_NONBLOCK": "fcntl.h", "O_NOCTTY": "fcntl.h",
            "O_SYNC": "fcntl.h", "SIGTERM": "signal.h", "SIGKILL": "signal.h",
            "SIGUSR1": "signal.h", "SIGUSR2": "signal.h", "SIGINT": "signal.h",
            "SIGSTOP": "signal.h", "EACCES": "errno.h", "ENOENT": "errno.h",
            "EINVAL": "errno.h", "EAGAIN": "errno.h", "ENOMEM": "errno.h",
            "WIFEXITED": "sys/wait.h", "WEXITSTATUS": "sys/wait.h",
            "WIFSIGNALED": "sys/wait.h", "WTERMSIG": "sys/wait.h",
            "STDOUT_FILENO": "unistd.h", "STDIN_FILENO": "unistd.h",
            "STDERR_FILENO": "unistd.h", "TCSAFLUSH": "termios.h",
            "TCSANOW": "termios.h", "TCSADRAIN": "termios.h", "BRKINT": "termios.h",
            "ICRNL": "termios.h", "INPCK": "termios.h", "ISTRIP": "termios.h",
            "IXON": "termios.h", "ECHO": "termios.h", "ICANON": "termios.h",
            "IEXTEN": "termios.h", "ISIG": "termios.h", "OPOST": "termios.h",
            "CS8": "termios.h", "VMIN": "termios.h", "VTIME": "termios.h",
            "TIOCGWINSZ": "sys/ioctl.h", "TIOCSWINSZ": "sys/ioctl.h",
        }

        # Look for include suggestions first
        include_pattern = r"note:.*is defined in header\s+['\u2018]<([^>]+)>['\u2019]"
        for inc_match in re.finditer(include_pattern, combined[match.start(): match.start() + 500]):
            include_name = inc_match.group(1).strip()

            # Try to find the associated error line
            error_context = combined[: match.start()]

            # Find the most recent filename:line reference
            file_pattern = r"^([a-zA-Z0-9_./\-]+\.c):(\d+):"
            file_matches = list(re.finditer(file_pattern, error_context, re.MULTILINE))

            if file_matches:
                last_match = file_matches[-1]
                source_file = last_match.group(1).strip()
                line_number = int(last_match.group(2))

                return ErrorClue(
                    clue_type="missing_c_include",
                    confidence=1.0,
                    context={
                        "file_path": source_file,
                        "line_number": line_number,
                        "suggested_include": include_name,
                    },
                    source_line=f"Suggested include: {include_name}",
                )

        # Look for undeclared identifiers without include suggestions
        if pattern_name == "c_undeclared":
            # Find the line containing this match
            line_start = combined.rfind('\n', 0, match.start()) + 1
            line_end = combined.find('\n', match.start())
            if line_end == -1:
                line_end = len(combined)
            
            error_line = combined[line_start:line_end]
            
            undeclared_pattern = r"^([a-zA-Z0-9_./\-]+\.c):(\d+):\d+:\s+error:\s+['\u2018]([^'\u2019]+)['\u2019]\s+undeclared\s+\(first use"
            
            und_match = re.match(undeclared_pattern, error_line)
            if und_match:
                source_file = und_match.group(1).strip()
                line_number = int(und_match.group(2))
                identifier = und_match.group(3).strip()

                # Check if this is a known stdlib constant/macro
                if identifier in stdlib_to_header:
                    header = stdlib_to_header[identifier]
                    return ErrorClue(
                        clue_type="missing_c_include",
                        confidence=0.95,
                        context={
                            "file_path": source_file,
                            "line_number": line_number,
                            "suggested_include": header,
                        },
                        source_line=error_line,
                    )
                else:
                    # Not a stdlib constant - likely a missing function definition
                    return ErrorClue(
                        clue_type="missing_c_function",
                        confidence=0.8,
                        context={
                            "file_path": source_file,
                            "line_number": line_number,
                            "symbols": [identifier],
                        },
                        source_line=error_line,
                    )

        return None

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

    @property
    def name(self) -> str:
        return "FopenNoSuchFileDetector"

    def detect(self, stderr: str, stdout: str = "") -> T.List[ErrorClue]:
        combined = stderr + "\n" + stdout

        if "fopen:" not in combined and "fopen: No such file or directory" not in combined:
            return []

        clues = []

        # Pattern 1: fopen: filename: No such file or directory
        pattern1 = r"fopen:\s+([^\s:]+?):\s*No such file or directory"
        for match in re.finditer(pattern1, combined):
            file_path = match.group(1).strip()
            clues.append(ErrorClue(
                clue_type="missing_file",
                confidence=0.95,
                context={"file_path": file_path},
                source_line=match.group(0)
            ))

        # Pattern 2: AssertionError mentioning a file that fopen can't open
        # Example: AssertionError: 'example.py' not found in 'fopen: No such file or directory'
        if "fopen: No such file or directory" in combined:
            assertion_pattern = r"AssertionError:\s*['\"]([^'\"]+\.py)['\"].*fopen: No such file or directory"
            for match in re.finditer(assertion_pattern, combined):
                file_path = match.group(1).strip()
                clues.append(ErrorClue(
                    clue_type="missing_file",
                    confidence=0.9,
                    context={"file_path": file_path},
                    source_line=f"fopen: No such file or directory (file: {file_path})"
                ))

        # Pattern 3: Test failures with fopen errors - extract filename from assertion
        # Example: AssertionError: 'Hello, World!' not found in 'fopen: No such file or directory'
        # The test name often indicates which file is being tested
        if "fopen: No such file or directory" in combined:
            # Look for test method names that indicate the file being tested
            # Example: test_open_file_and_view_contents, test_open_readme_and_view_first_line
            test_patterns = [
                (r"test_open_file_and_view_contents", ["hello_world.txt"]),
                (r"test_open_readme", ["README.md"]),
                (r"test_status_bar_shows_filename_and_lines", ["hello_world.txt"]),
                (r"test_navigation_with_arrow_keys", ["hello_world.txt"]),
                (r"test_syntax_highlighting_c", ["example.c"]),
                (r"test_modified_indicator", ["hello_world.txt"]),
            ]

            for test_pattern, possible_files in test_patterns:
                if re.search(test_pattern, combined):
                    for file_path in possible_files:
                        if not any(c.context.get("file_path") == file_path for c in clues):
                            clues.append(ErrorClue(
                                clue_type="missing_file",
                                confidence=0.8,
                                context={"file_path": file_path},
                                source_line=f"fopen: No such file or directory (inferred from {test_pattern})"
                            ))

        # Pattern 4: Fallback - look for any file with extension mentioned in context
        if not clues and "fopen: No such file or directory" in combined:
            # Look for filenames with common extensions in the error output
            # This handles cases where the filename is mentioned elsewhere in the test output
            file_pattern = r'\b([a-zA-Z0-9_-]+\.(?:txt|md|py|c|h|cpp|cc|java|js|html|css))\b'
            matches = list(re.finditer(file_pattern, combined))

            # Get unique filenames
            seen_files = set()
            for match in matches:
                file_path = match.group(1).strip()
                if file_path not in seen_files and not any(c.context.get("file_path") == file_path for c in clues):
                    seen_files.add(file_path)
                    clues.append(ErrorClue(
                        clue_type="missing_file",
                        confidence=0.6,
                        context={"file_path": file_path},
                        source_line="fopen: No such file or directory (inferred from context)"
                    ))

        return clues


class FileNotFoundDetector(Detector):
    """
    Detect FileNotFoundError in various formats.

    Matches patterns like:
    - FileNotFoundError: [Errno 2] No such file or directory: './test.sh'
    - FileNotFoundError: ./test.sh
    """

    @property
    def name(self) -> str:
        return "FileNotFoundDetector"

    def detect(self, stderr: str, stdout: str = "") -> T.List[ErrorClue]:
        combined = stderr + "\n" + stdout

        if "FileNotFoundError" not in combined:
            return []

        clues = []

        # Pattern 1: FileNotFoundError: [Errno 2] No such file or directory: './file'
        pattern1 = r"FileNotFoundError:.*?No such file or directory:\s*['\"]([^'\"]+)['\"]"
        for match in re.finditer(pattern1, combined):
            file_path = match.group(1).strip()
            clues.append(ErrorClue(
                clue_type="missing_file",
                confidence=1.0,
                context={"file_path": file_path},
                source_line=match.group(0)
            ))

        # Pattern 2: FileNotFoundError: ./file
        if not clues:  # Only try if pattern1 didn't match
            pattern2 = r"FileNotFoundError:\s*([^\s:]+)"
            for match in re.finditer(pattern2, combined):
                file_path = match.group(1).strip()
                clues.append(ErrorClue(
                    clue_type="missing_file",
                    confidence=0.9,
                    context={"file_path": file_path},
                    source_line=match.group(0)
                ))

        return clues


class ShellCannotOpenDetector(Detector):
    """
    Detect shell errors when a file cannot be opened.

    Matches patterns like:
    - sh: 0: cannot open makeoptions: No such file
    - /bin/sh: cannot open file: No such file
    """

    @property
    def name(self) -> str:
        return "ShellCannotOpenDetector"

    def detect(self, stderr: str, stdout: str = "") -> T.List[ErrorClue]:
        combined = stderr + "\n" + stdout

        if "cannot open" not in combined:
            return []

        clues = []

        # Pattern: sh: N: cannot open filename: No such file
        pattern = r"sh:\s*\d+:\s*cannot open\s+([^\s:]+):\s*No such file"
        for match in re.finditer(pattern, combined):
            file_path = match.group(1).strip()
            clues.append(ErrorClue(
                clue_type="missing_file",
                confidence=1.0,
                context={"file_path": file_path},
                source_line=match.group(0)
            ))

        return clues


class ShellCommandNotFoundDetector(Detector):
    """
    Detect shell errors when a command/script is not found.

    Matches patterns like:
    - ./test.sh: line 3: ./configure: No such file or directory
    - ./test.sh: 2: ./configure: not found
    - /bin/sh: ./script.sh: not found
    """

    @property
    def name(self) -> str:
        return "ShellCommandNotFoundDetector"

    def detect(self, stderr: str, stdout: str = "") -> T.List[ErrorClue]:
        combined = stderr + "\n" + stdout

        if "not found" not in combined and "No such file or directory" not in combined:
            return []

        clues = []

        # Pattern 1: line N: ./command: No such file or directory
        pattern1 = r":\s*line\s+\d+:\s*([^\s:]+):\s*No such file or directory"
        for match in re.finditer(pattern1, combined):
            file_path = match.group(1).strip()
            if file_path.startswith("./"):
                file_path = file_path[2:]
            clues.append(ErrorClue(
                clue_type="missing_file",
                confidence=1.0,
                context={"file_path": file_path},
                source_line=match.group(0)
            ))

        # Pattern 2: N: ./command: not found
        pattern2 = r":\s*\d+:\s*([^\s:]+):\s*not found"
        for match in re.finditer(pattern2, combined):
            file_path = match.group(1).strip()
            if file_path.startswith("./"):
                file_path = file_path[2:]
            # Avoid duplicates
            if not any(c.context.get("file_path") == file_path for c in clues):
                clues.append(ErrorClue(
                    clue_type="missing_file",
                    confidence=0.9,
                    context={"file_path": file_path},
                    source_line=match.group(0)
                ))

        return clues


class CatNoSuchFileDetector(Detector):
    """
    Detect cat errors when a file is missing.

    Matches patterns like:
    - cat: Makefile.in: No such file or directory
    """

    @property
    def name(self) -> str:
        return "CatNoSuchFileDetector"

    def detect(self, stderr: str, stdout: str = "") -> T.List[ErrorClue]:
        combined = stderr + "\n" + stdout

        if "cat:" not in combined:
            return []

        clues = []

        # Pattern: cat: filename: No such file or directory
        pattern = r"cat:\s*([^\s:]+):\s*No such file or directory"
        for match in re.finditer(pattern, combined):
            file_path = match.group(1).strip()
            clues.append(ErrorClue(
                clue_type="missing_file",
                confidence=1.0,
                context={"file_path": file_path},
                source_line=match.group(0)
            ))

        return clues


class DiffNoSuchFileDetector(Detector):
    """
    Detect diff errors when a file is missing.

    Matches patterns like:
    - diff: test.txt: No such file or directory
    """

    @property
    def name(self) -> str:
        return "DiffNoSuchFileDetector"

    def detect(self, stderr: str, stdout: str = "") -> T.List[ErrorClue]:
        combined = stderr + "\n" + stdout

        if "diff:" not in combined:
            return []

        clues = []

        # Pattern: diff: filename: No such file or directory
        pattern = r"diff:\s*([^\s:]+):\s*No such file or directory"
        for match in re.finditer(pattern, combined):
            file_path = match.group(1).strip()
            clues.append(ErrorClue(
                clue_type="missing_file",
                confidence=1.0,
                context={"file_path": file_path},
                source_line=match.group(0)
            ))

        return clues


class CLinkerErrorDetector(Detector):
    """
    Detect C/C++ linker errors when object files or libraries are missing.

    Matches patterns like:
    - /usr/bin/ld: /tmp/cckoAdDP.o: in function `print_node_text':
    - tree_print.c:(.text+0x137): undefined reference to `ts_node_start_byte'
    - /usr/bin/ld: cannot find -lsomelibrary: No such file or directory
    """

    @property
    def name(self) -> str:
        return "CLinkerErrorDetector"

    def detect(self, stderr: str, stdout: str = "") -> T.List[ErrorClue]:
        combined = stderr + "\n" + stdout

        # Check if this is a linker error
        if "undefined reference to" not in combined and "cannot find" not in combined:
            return []

        clues = []

        # Pattern 1: undefined reference to symbol
        # Example: undefined reference to `ts_parser_new'
        if "undefined reference to" in combined:
            # Extract all undefined symbols
            undefined_symbols = set()
            pattern = r"undefined reference to [`']([^'`]+)[`']"
            for match in re.finditer(pattern, combined):
                symbol = match.group(1)
                undefined_symbols.add(symbol)

            if undefined_symbols:
                clues.append(ErrorClue(
                    clue_type="linker_undefined_symbols",
                    confidence=1.0,
                    context={"symbols": list(undefined_symbols)},
                    source_line=f"Found {len(undefined_symbols)} undefined references"
                ))

        # Pattern 3: cannot find object file (check this first as it's more specific)
        # Example: /usr/bin/ld: cannot find exrecover.o: No such file or directory
        pattern3 = r"cannot find\s+([^\s:]+\.o):\s+No such file or directory"
        for match in re.finditer(pattern3, combined):
            obj_file = match.group(1).strip()
            clues.append(ErrorClue(
                clue_type="missing_object_file",
                confidence=1.0,
                context={"object_file": obj_file},
                source_line=match.group(0)
            ))

        # Pattern 2: cannot find library (only if it's not an object file)
        # Example: /usr/bin/ld: cannot find -lsomelibrary: No such file or directory
        pattern2 = r"cannot find\s+([^\s:]+):\s+No such file or directory"
        for match in re.finditer(pattern2, combined):
            library = match.group(1).strip()
            # Skip if already matched as object file
            if library.endswith('.o'):
                continue
            clues.append(ErrorClue(
                clue_type="missing_library",
                confidence=1.0,
                context={"library": library},
                source_line=match.group(0)
            ))

        return clues


class CCompilationErrorDetector(Detector):
    """
    Detect C/C++ compilation errors when header files are missing.

    Matches patterns like:
    - /tmp/ex_bar.c:82:10: fatal error: ex.h: No such file or directory
    -    82 | #include "ex.h"
    - lib/src/node.c:2:10: fatal error: ./point.h: No such file or directory
    """

    @property
    def name(self) -> str:
        return "CCompilationErrorDetector"

    def detect(self, stderr: str, stdout: str = "") -> T.List[ErrorClue]:
        combined = stderr + "\n" + stdout

        if "fatal error:" not in combined:
            return []

        clues = []

        # Pattern: fatal error: filename: No such file or directory
        pattern = r"fatal error:\s+([^\s:]+):\s+No such file or directory"
        
        # Try to find the source file being compiled - look for patterns like:
        # cc ... lib/src/node.c
        # gcc -o tree_print tree_print.c ...
        source_file_pattern = r"(?:cc|gcc|clang|g\+\+|c\+\+)\s+[^:]*?\s+([^\s]+\.c+)\s+"
        
        for match in re.finditer(pattern, combined):
            file_path = match.group(1).strip()
            # Remove ./ prefix if present
            if file_path.startswith("./"):
                file_path = file_path[2:]
            
            context = {
                "file_path": file_path,
                "is_header": file_path.endswith(".h"),
            }
            
            # Try to find the source file being compiled for better context
            source_match = re.search(source_file_pattern, combined)
            if source_match:
                source_file = source_match.group(1).strip()
                context["source_file"] = source_file
                # Extract the directory of the source file to search for the header
                import os
                source_dir = os.path.dirname(source_file)
                if source_dir:
                    context["source_dir"] = source_dir
            
            clues.append(ErrorClue(
                clue_type="missing_file",
                confidence=1.0,
                context=context,
                source_line=match.group(0)
            ))

        return clues


class CIncompleteTypeDetector(Detector):
    """
    Detect C compilation errors for incomplete struct/type errors.

    Matches patterns like:
    - error: field 'orig_termios' has incomplete type
    - error: storage size of 'raw' isn't known
    - These usually indicate missing header files for struct definitions
    """

    @property
    def name(self) -> str:
        return "CIncompleteTypeDetector"

    def detect(self, stderr: str, stdout: str = "") -> T.List[ErrorClue]:
        combined = stderr + "\n" + stdout

        if "incomplete type" not in combined and "storage size" not in combined:
            return []

        clues = []

        # Map incomplete types to likely headers
        type_to_header = {
            'termios': 'termios.h',
            'winsize': 'sys/ioctl.h',
            'stat': 'sys/stat.h',
            'tm': 'time.h',
            'sigaction': 'signal.h',
            'dirent': 'dirent.h',
        }

        # Pattern for incomplete type errors
        # error: field 'name' has incomplete type
        incomplete_pattern = r"error:.*has incomplete type"
        
        # Pattern to extract struct name - look for struct keyword
        # struct termios orig_termios;
        struct_pattern = r"struct\s+([a-zA-Z_][a-zA-Z0-9_]*)"

        # Find all incomplete type errors and look for struct names nearby
        for match in re.finditer(incomplete_pattern, combined):
            error_context = combined[max(0, match.start() - 200):match.end() + 100]
            
            # Find the most recent struct declaration in context
            struct_matches = list(re.finditer(struct_pattern, error_context))
            if struct_matches:
                struct_name = struct_matches[-1].group(1)
                
                # Check if we know which header this struct needs
                if struct_name in type_to_header:
                    header = type_to_header[struct_name]
                    
                    # Try to find the source file
                    file_pattern = r"^([a-zA-Z0-9_./\-]+\.c):(\d+):"
                    file_matches = list(re.finditer(file_pattern, combined[:match.start()], re.MULTILINE))
                    
                    source_file = "unknown"
                    line_number = 0
                    if file_matches:
                        last_match = file_matches[-1]
                        source_file = last_match.group(1).strip()
                        line_number = int(last_match.group(2))
                    
                    clues.append(ErrorClue(
                        clue_type="missing_c_include",
                        confidence=0.9,
                        context={
                            "file_path": source_file,
                            "line_number": line_number,
                            "struct_name": struct_name,
                            "suggested_include": header,
                        },
                        source_line=match.group(0)
                    ))

        return clues


class CImplicitDeclarationDetector(Detector):
    """
    Detect C implicit function declaration errors that suggest missing includes.

    Matches patterns like:
    - error: implicit declaration of function 'printf' [-Werror=implicit-function-declaration]
    - note: include '<stdio.h>' or provide a declaration of 'printf'
    """

    @property
    def name(self) -> str:
        return "CImplicitDeclarationDetector"

    def detect(self, stderr: str, stdout: str = "") -> T.List[ErrorClue]:
        combined = stderr + "\n" + stdout

        if "implicit declaration of function" not in combined:
            return []

        clues = []

        # Map stdlib functions to their headers
        stdlib_to_header = {
            # stdio.h
            'printf': 'stdio.h', 'fprintf': 'stdio.h', 'sprintf': 'stdio.h', 'scanf': 'stdio.h',
            'fscanf': 'stdio.h', 'fopen': 'stdio.h', 'fclose': 'stdio.h', 'fread': 'stdio.h',
            'fwrite': 'stdio.h', 'fgets': 'stdio.h', 'fputs': 'stdio.h', 'getchar': 'stdio.h',
            'putchar': 'stdio.h', 'puts': 'stdio.h', 'gets': 'stdio.h', 'sscanf': 'stdio.h',
            'snprintf': 'stdio.h', 'perror': 'stdio.h',
            # stdlib.h
            'malloc': 'stdlib.h', 'calloc': 'stdlib.h', 'realloc': 'stdlib.h', 'free': 'stdlib.h',
            'atoi': 'stdlib.h', 'atol': 'stdlib.h', 'strtol': 'stdlib.h', 'rand': 'stdlib.h',
            'srand': 'stdlib.h', 'exit': 'stdlib.h', 'abort': 'stdlib.h', 'atexit': 'stdlib.h',
            # string.h
            'strlen': 'string.h', 'strcpy': 'string.h', 'strncpy': 'string.h', 'strcat': 'string.h', 
            'strncat': 'string.h', 'strcmp': 'string.h', 'strncmp': 'string.h', 'strchr': 'string.h', 
            'strstr': 'string.h', 'memcpy': 'string.h', 'memmove': 'string.h', 'memset': 'string.h', 
            'memcmp': 'string.h',
            # unistd.h
            'read': 'unistd.h', 'write': 'unistd.h', 'open': 'unistd.h', 'close': 'unistd.h', 
            'lseek': 'unistd.h', 'fork': 'unistd.h', 'exit': 'unistd.h', 'sleep': 'unistd.h', 
            'usleep': 'unistd.h',
            # fcntl.h
            'fcntl': 'fcntl.h', 'dup': 'fcntl.h', 'dup2': 'fcntl.h',
            # signal.h
            'signal': 'signal.h', 'kill': 'signal.h', 'raise': 'signal.h', 'pause': 'signal.h',
            # sys/stat.h
            'stat': 'sys/stat.h', 'fstat': 'sys/stat.h', 'lstat': 'sys/stat.h', 
            'chmod': 'sys/stat.h', 'mkdir': 'sys/stat.h',
            # time.h
            'time': 'time.h', 'localtime': 'time.h', 'gmtime': 'time.h', 'strftime': 'time.h', 
            'clock': 'time.h',
            # stdarg.h
            'va_start': 'stdarg.h', 'va_end': 'stdarg.h', 'va_arg': 'stdarg.h', 'va_copy': 'stdarg.h',
            # math.h
            'sin': 'math.h', 'cos': 'math.h', 'tan': 'math.h', 'sqrt': 'math.h', 'pow': 'math.h', 
            'abs': 'math.h', 'fabs': 'math.h',
            # ctype.h
            'isalpha': 'ctype.h', 'isdigit': 'ctype.h', 'isspace': 'ctype.h', 
            'tolower': 'ctype.h', 'toupper': 'ctype.h',
            # termios.h
            'tcgetattr': 'termios.h', 'tcsetattr': 'termios.h',
            # sys/ioctl.h
            'ioctl': 'sys/ioctl.h',
        }

        # Pattern for implicit declaration error
        # example.c:5:5: error: implicit declaration of function 'printf'
        # Note: Support both regular ' and Unicode ' quotes
        # Only match lines that start with a path-like pattern (no leading spaces/brackets)
        implicit_pattern = r"^([a-zA-Z0-9_./\-]+\.c):(\d+):\d+:\s+(?:error|warning):\s+implicit declaration of function ['\u2018]([^'\u2019]+)['\u2019]"

        # Pattern for include suggestion - format 1
        # note: include '<stdio.h>' or provide a declaration of 'printf'
        # Capture both the header and the symbol it's for
        include_pattern1 = r"note:\s+include\s+['\u2018]<([^>]+)>['\u2019]\s+or provide a declaration of ['\u2018]([^'\u2019]+)['\u2019]"

        # Pattern for include suggestion - format 2
        # note: 'NULL' is defined in header '<stddef.h>'; did you forget to '#include <stddef.h>'?
        # Capture both the symbol and the header
        include_pattern2 = r"note:\s+['\u2018]([^'\u2019]+)['\u2019]\s+is defined in header\s+['\u2018]<([^>]+)>['\u2019]"

        # Find all implicit declarations
        implicit_matches = list(re.finditer(implicit_pattern, combined, re.MULTILINE))
        # Note: For pattern1, group(1)=header, group(2)=symbol
        # For pattern2, group(1)=symbol, group(2)=header
        include_matches1 = list(re.finditer(include_pattern1, combined))
        include_matches2 = list(re.finditer(include_pattern2, combined))
        include_matches = [(m, m.group(1), m.group(2)) for m in include_matches1]  # (match, header, symbol)
        include_matches += [(m, m.group(2), m.group(1)) for m in include_matches2]  # (match, header, symbol)

        # Match them up - the include suggestion usually comes after the error
        for i, implicit_match in enumerate(implicit_matches):
            source_file = implicit_match.group(1).strip()
            line_number = int(implicit_match.group(2))
            function_name = implicit_match.group(3).strip()

            # Try to find the corresponding include suggestion that appears AFTER this error
            # AND is for the SAME symbol
            include_name = None
            implicit_end_pos = implicit_match.end()
            for match_tuple in include_matches:
                inc_match, header, symbol = match_tuple
                if inc_match.start() > implicit_end_pos:
                    # Found an include suggestion after this error
                    # Check if it's close enough (within ~500 chars) and for the same symbol
                    if inc_match.start() - implicit_end_pos < 500 and symbol == function_name:
                        include_name = header.strip()
                        break

            context = {
                "file_path": source_file,
                "line_number": line_number,
                "function_name": function_name,
            }

            # If there's a suggested include, it's a missing include problem
            if include_name:
                context["suggested_include"] = include_name
                clues.append(ErrorClue(
                    clue_type="missing_c_include",
                    confidence=1.0,
                    context=context,
                    source_line=implicit_match.group(0)
                ))
            # Check if it's a known stdlib function - if so, look it up in the mapping
            elif function_name in stdlib_to_header:
                context["suggested_include"] = stdlib_to_header[function_name]
                clues.append(ErrorClue(
                    clue_type="missing_c_include",
                    confidence=0.95,
                    context=context,
                    source_line=implicit_match.group(0)
                ))
            else:
                # No include suggestion and not a stdlib function - likely a missing function definition
                clues.append(ErrorClue(
                    clue_type="missing_c_function",
                    confidence=0.8,
                    context={
                        "file_path": source_file,
                        "symbols": [function_name],
                    },
                    source_line=implicit_match.group(0)
                ))

        return clues


class CUndeclaredIdentifierDetector(Detector):
    """
    Detect C compilation errors for undeclared identifiers with include suggestions.

    Matches patterns like:
    - error: 'NULL' undeclared here (not in a function)
    - note: 'NULL' is defined in header '<stddef.h>'; did you forget to '#include <stddef.h>'?
    
    Also detects undeclared identifiers without include suggestions (missing functions):
    - error: 'disableRawMode' undeclared (first use in this function)
    """

    @property
    def name(self) -> str:
        return "CUndeclaredIdentifierDetector"

    def detect(self, stderr: str, stdout: str = "") -> T.List[ErrorClue]:
        combined = stderr + "\n" + stdout

        if "undeclared" not in combined and "unknown type name" not in combined:
            return []

        clues = []

        # Pattern for include suggestions
        # note: 'NULL' is defined in header '<stddef.h>'; did you forget to '#include <stddef.h>'?
        # note: 'atexit' is defined in header '<stdlib.h>'; did you forget to '#include <stdlib.h>'?
        include_pattern = r"note:.*is defined in header\s+['\u2018]<([^>]+)>['\u2019]"

        # Find all include suggestions
        for match in re.finditer(include_pattern, combined):
            include_name = match.group(1).strip()

            # Try to find the associated error line (should be a few lines before)
            # Look backwards from this position
            error_context = combined[:match.start()]

            # Find the most recent filename:line reference
            file_pattern = r"^([a-zA-Z0-9_./\-]+\.c):(\d+):"
            file_matches = list(re.finditer(file_pattern, error_context, re.MULTILINE))

            if file_matches:
                last_match = file_matches[-1]
                source_file = last_match.group(1).strip()
                line_number = int(last_match.group(2))

                clues.append(ErrorClue(
                    clue_type="missing_c_include",
                    confidence=1.0,
                    context={
                        "file_path": source_file,
                        "line_number": line_number,
                        "suggested_include": include_name,
                    },
                    source_line=f"Suggested include: {include_name}"
                ))

        # Also detect undeclared identifiers without include suggestions (missing functions)
        # Pattern: filename.c:line:col: error: 'identifier' undeclared (first use in this function)
        # Note: GCC may output fancy Unicode quotes (') so we need to match both ASCII and Unicode quotes
        
        # Map stdlib constants/macros to their headers
        stdlib_to_header = {
            # fcntl.h
            'O_RDWR': 'fcntl.h', 'O_RDONLY': 'fcntl.h', 'O_WRONLY': 'fcntl.h', 
            'O_CREAT': 'fcntl.h', 'O_APPEND': 'fcntl.h', 'O_EXCL': 'fcntl.h', 'O_TRUNC': 'fcntl.h',
            'O_NONBLOCK': 'fcntl.h', 'O_NOCTTY': 'fcntl.h', 'O_SYNC': 'fcntl.h',
            # signal.h
            'SIGTERM': 'signal.h', 'SIGKILL': 'signal.h', 'SIGUSR1': 'signal.h', 
            'SIGUSR2': 'signal.h', 'SIGINT': 'signal.h', 'SIGSTOP': 'signal.h',
            # errno.h
            'EACCES': 'errno.h', 'ENOENT': 'errno.h', 'EINVAL': 'errno.h', 
            'EAGAIN': 'errno.h', 'ENOMEM': 'errno.h',
            # sys/wait.h
            'WIFEXITED': 'sys/wait.h', 'WEXITSTATUS': 'sys/wait.h', 
            'WIFSIGNALED': 'sys/wait.h', 'WTERMSIG': 'sys/wait.h',
            # unistd.h
            'STDOUT_FILENO': 'unistd.h', 'STDIN_FILENO': 'unistd.h', 'STDERR_FILENO': 'unistd.h',
            # termios.h
            'TCSAFLUSH': 'termios.h', 'TCSANOW': 'termios.h', 'TCSADRAIN': 'termios.h',
            'BRKINT': 'termios.h', 'ICRNL': 'termios.h', 'INPCK': 'termios.h', 
            'ISTRIP': 'termios.h', 'IXON': 'termios.h',
            'ECHO': 'termios.h', 'ICANON': 'termios.h', 'IEXTEN': 'termios.h', 'ISIG': 'termios.h',
            'OPOST': 'termios.h', 'CS8': 'termios.h', 'VMIN': 'termios.h', 'VTIME': 'termios.h',
            # sys/ioctl.h
            'TIOCGWINSZ': 'sys/ioctl.h', 'TIOCSWINSZ': 'sys/ioctl.h',
        }
        
        undeclared_no_include_pattern = r"^([a-zA-Z0-9_./\-]+\.c):(\d+):\d+:\s+error:\s+['\u2018]([^'\u2019]+)['\u2019]\s+undeclared\s+\(first use"
        
        # Find all undeclared identifiers without include suggestions
        for match in re.finditer(undeclared_no_include_pattern, combined, re.MULTILINE):
            source_file = match.group(1).strip()
            line_number = int(match.group(2))
            identifier = match.group(3).strip()

            # Only add if we haven't already added an include suggestion for this identifier
            # (avoid duplicates)
            already_has_include = any(
                c.clue_type == "missing_c_include" and 
                c.context.get("file_path") == source_file and
                identifier in c.context.get("suggested_include", "")
                for c in clues
            )
            
            # Check if this is a known stdlib constant/macro with a known header
            if identifier in stdlib_to_header and not already_has_include:
                header = stdlib_to_header[identifier]
                clues.append(ErrorClue(
                    clue_type="missing_c_include",
                    confidence=0.95,
                    context={
                        "file_path": source_file,
                        "line_number": line_number,
                        "suggested_include": header,
                    },
                    source_line=match.group(0)
                ))
            elif not already_has_include and not identifier in stdlib_to_header:
                # Not a stdlib constant - likely a missing function definition
                clues.append(ErrorClue(
                    clue_type="missing_c_function",
                    confidence=0.8,
                    context={
                        "file_path": source_file,
                        "line_number": line_number,
                        "symbols": [identifier],
                    },
                    source_line=match.group(0)
                ))

        return clues

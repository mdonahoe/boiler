"""
Planners for restoring missing C code (includes, functions).
"""

import os
import typing as T
from pipeline.planners.base import Planner
from pipeline.models import ErrorClue, RepairPlan, GitState


class MissingCFunctionPlanner(Planner):
    """
    Plan fixes for missing C function definitions (implicit declarations).

    Strategy:
    - Target files where function is implicitly declared
    - Use src_repair to restore the missing function definition
    - Filter out stdlib functions/constants/macros that won't be in git history
    """

    # Known stdlib functions and constants mapped to their headers
    # These should not be restored from git but should trigger include suggestions
    STDLIB_SYMBOL_TO_HEADER = {
        # unistd.h - POSIX I/O functions and constants
        "read": "unistd.h", "write": "unistd.h", "open": "unistd.h", "close": "unistd.h",
        "lseek": "unistd.h", "dup": "unistd.h", "dup2": "unistd.h", "pipe": "unistd.h",
        "ftruncate": "unistd.h", "truncate": "unistd.h", "fsync": "unistd.h", "fdatasync": "unistd.h",
        "STDIN_FILENO": "unistd.h", "STDOUT_FILENO": "unistd.h", "STDERR_FILENO": "unistd.h",
        # fcntl.h - File control
        "fcntl": "fcntl.h", "O_RDONLY": "fcntl.h", "O_WRONLY": "fcntl.h", "O_RDWR": "fcntl.h",
        "O_CREAT": "fcntl.h", "O_EXCL": "fcntl.h", "O_TRUNC": "fcntl.h", "O_APPEND": "fcntl.h",
        "O_NONBLOCK": "fcntl.h", "O_SYNC": "fcntl.h", "O_ASYNC": "fcntl.h", "O_DIRECTORY": "fcntl.h",
        # sys/ioctl.h - Terminal/device control
        "ioctl": "sys/ioctl.h", "TIOCGWINSZ": "sys/ioctl.h", "TIOCSWINSZ": "sys/ioctl.h",
        # termios.h - Terminal I/O
        "tcgetattr": "termios.h", "tcsetattr": "termios.h", "tcsendbreak": "termios.h",
        "tcdrain": "termios.h", "tcflush": "termios.h", "tcflow": "termios.h",
        "cfgetospeed": "termios.h", "cfgetispeed": "termios.h",
        "cfsetospeed": "termios.h", "cfsetispeed": "termios.h",
        "TCSANOW": "termios.h", "TCSADRAIN": "termios.h", "TCSAFLUSH": "termios.h",
        "BRKINT": "termios.h", "ICRNL": "termios.h", "INPCK": "termios.h",
        "ISTRIP": "termios.h", "IXON": "termios.h", "OPOST": "termios.h", "CS8": "termios.h",
        "CSIZE": "termios.h", "CSTOPB": "termios.h", "CREAD": "termios.h",
        "PARENB": "termios.h", "PARODD": "termios.h", "HUPCL": "termios.h", "CLOCAL": "termios.h",
        "ECHO": "termios.h", "ECHOE": "termios.h", "ECHOK": "termios.h", "ECHONL": "termios.h",
        "ICANON": "termios.h", "IEXTEN": "termios.h", "ISIG": "termios.h",
        "VMIN": "termios.h", "VTIME": "termios.h", "VEOF": "termios.h", "VEOL": "termios.h",
        "VERASE": "termios.h", "VINTR": "termios.h", "VKILL": "termios.h", "VQUIT": "termios.h",
        "VSTART": "termios.h", "VSTOP": "termios.h", "VSUSP": "termios.h",
        # stdlib.h
        "exit": "stdlib.h", "atexit": "stdlib.h", "malloc": "stdlib.h", "free": "stdlib.h",
        "realloc": "stdlib.h", "calloc": "stdlib.h",
        # stdio.h
        "fopen": "stdio.h", "fclose": "stdio.h", "fread": "stdio.h", "fwrite": "stdio.h",
        "fprintf": "stdio.h", "printf": "stdio.h", "sprintf": "stdio.h", "snprintf": "stdio.h",
        "perror": "stdio.h", "getline": "stdio.h",
        # string.h
        "strdup": "string.h", "strlen": "string.h", "strcmp": "string.h", "strncmp": "string.h",
        "strcpy": "string.h", "strncpy": "string.h", "strcat": "string.h", "strncat": "string.h",
        "strchr": "string.h", "strrchr": "string.h", "strstr": "string.h",
        "memcpy": "string.h", "memmove": "string.h", "memset": "string.h", "memcmp": "string.h",
        "strerror": "string.h",
        # errno.h
        "errno": "errno.h", "EAGAIN": "errno.h", "EINTR": "errno.h",
    }

    @property
    def name(self) -> str:
        return "MissingCFunctionPlanner"

    def can_handle(self, clue_type: str) -> bool:
        return clue_type == "missing_c_function"

    def plan(self, clues: T.List[ErrorClue], git_state: GitState) -> T.List[RepairPlan]:
        plans = []
        for clue in clues:
            if clue.clue_type != "missing_c_function":
                continue
            plans.extend(self._plan_for_clue(clue, git_state))
        return plans

    def _plan_for_clue(self, clue: ErrorClue, git_state: GitState) -> T.List[RepairPlan]:
        file_path = clue.context.get("file_path")

        # Handle both old format (symbols list) and new format (single identifier)
        symbols = clue.context.get("symbols", [])
        if not symbols and "identifier" in clue.context:
            symbols = [clue.context["identifier"]]
        elif not symbols and "function_name" in clue.context:
            symbols = [clue.context["function_name"]]

        if not file_path or not symbols:
            print(f"[Planner:MissingCFunctionPlanner] Missing file_path or symbols")
            return []

        # Make path relative if it's absolute
        if os.path.isabs(file_path):
            file_path = os.path.relpath(file_path)

        # Only plan repairs for files that exist
        if not os.path.exists(file_path):
            print(f"[Planner:MissingCFunctionPlanner] File {file_path} does not exist, skipping")
            return []

        # Separate stdlib symbols from user-defined symbols
        stdlib_symbols = [s for s in symbols if s in self.STDLIB_SYMBOL_TO_HEADER]
        user_symbols = [s for s in symbols if s not in self.STDLIB_SYMBOL_TO_HEADER]

        if stdlib_symbols:
            print(f"[Planner:MissingCFunctionPlanner] Found stdlib symbols needing includes: {stdlib_symbols}")
        if user_symbols:
            print(f"[Planner:MissingCFunctionPlanner] Planning to restore {len(user_symbols)} user function(s) to {file_path}")

        # Create plans
        plans = []

        # For stdlib symbols, create include restoration plans instead of function restoration
        # Group by header to avoid duplicate include plans
        headers_needed = {}
        for symbol in stdlib_symbols:
            header = self.STDLIB_SYMBOL_TO_HEADER[symbol]
            if header not in headers_needed:
                headers_needed[header] = []
            headers_needed[header].append(symbol)

        for header, syms in headers_needed.items():
            # Check if the include is already present in the file
            try:
                with open(file_path, 'r') as f:
                    content = f.read()
                    if f'#include <{header}>' in content or f'#include "{header}"' in content:
                        print(f"[Planner:MissingCFunctionPlanner] Include <{header}> already present, skipping")
                        continue
            except Exception as e:
                print(f"[Planner:MissingCFunctionPlanner] Error reading {file_path}: {e}")
                continue

            plans.append(RepairPlan(
                plan_type="restore_c_code",
                priority=0,  # High priority - compilation error
                target_file=file_path,
                action="restore_c_element",
                params={
                    "ref": git_state.ref,
                    "element_name": header,
                    "element_type": "include",
                },
                reason=f"Missing #include <{header}> for stdlib symbols {', '.join(syms[:3])}{'...' if len(syms) > 3 else ''} in {file_path}",
                clue_source=clue
            ))

        # For user-defined symbols, create function restoration plans
        for symbol in user_symbols:
            plans.append(RepairPlan(
                plan_type="restore_c_code",
                priority=0,  # High priority - compilation error
                target_file=file_path,
                action="restore_c_element",
                params={
                    "ref": git_state.ref,
                    "element_name": symbol,
                    "element_type": "function",
                },
                reason=f"Missing function definition '{symbol}' in {file_path}",
                clue_source=clue
            ))

        return plans


class MissingCIncludePlanner(Planner):
    """
    Plan fixes for missing C includes (implicit function declarations).

    Strategy:
    - Target only files that exist (not deleted files)
    - Use src_repair to restore the missing #include directive
    """

    @property
    def name(self) -> str:
        return "MissingCIncludePlanner"

    def can_handle(self, clue_type: str) -> bool:
        return clue_type == "missing_c_include"

    def plan(self, clues: T.List[ErrorClue], git_state: GitState) -> T.List[RepairPlan]:
        plans = []
        for clue in clues:
            if clue.clue_type != "missing_c_include":
                continue
            plans.extend(self._plan_for_clue(clue, git_state))
        return plans

    def _plan_for_clue(self, clue: ErrorClue, git_state: GitState) -> T.List[RepairPlan]:
        file_path = clue.context.get("file_path")
        suggested_include = clue.context.get("suggested_include")
        function_name = clue.context.get("function_name")
        struct_name = clue.context.get("struct_name")

        if not file_path:
            print(f"[Planner:MissingCIncludePlanner] Missing file_path")
            return []

        # Make path relative if it's absolute
        if os.path.isabs(file_path):
            file_path = os.path.relpath(file_path)

        # Only plan repairs for files that exist
        if not os.path.exists(file_path):
            print(f"[Planner:MissingCIncludePlanner] File {file_path} does not exist, skipping")
            return []

        # Map struct names to their required headers if not suggested
        STRUCT_TO_HEADER = {
            "termios": "termios.h",
            "winsize": "sys/ioctl.h",
            "stat": "sys/stat.h",
            "tm": "time.h",
            "sigaction": "signal.h",
            "dirent": "dirent.h",
        }

        # If we have a suggested include, use it; otherwise try to map from struct name
        if not suggested_include:
            if struct_name and struct_name in STRUCT_TO_HEADER:
                suggested_include = STRUCT_TO_HEADER[struct_name]
                print(f"[Planner:MissingCIncludePlanner] Mapped struct '{struct_name}' to header '{suggested_include}'")
            else:
                print(f"[Planner:MissingCIncludePlanner] No suggested include and can't map struct '{struct_name}', skipping")
                return []

        # Check if the include is already present in the file
        try:
            with open(file_path, 'r') as f:
                content = f.read()
                # Check for both <header.h> and "header.h" styles
                if f'#include <{suggested_include}>' in content or f'#include "{suggested_include}"' in content:
                    print(f"[Planner:MissingCIncludePlanner] Include <{suggested_include}> already present in {file_path}, skipping")
                    return []
        except Exception as e:
            print(f"[Planner:MissingCIncludePlanner] Error reading {file_path}: {e}")
            return []

        reason_detail = f"function '{function_name}'" if function_name else f"struct '{struct_name}'"
        print(f"[Planner:MissingCIncludePlanner] Planning to restore '#include <{suggested_include}>' to {file_path}")

        return [
            RepairPlan(
                plan_type="restore_c_code",
                priority=0,  # High priority - compilation failure
                target_file=file_path,
                action="restore_c_element",
                params={
                    "ref": git_state.ref,
                    "element_name": suggested_include,
                    "element_type": "include",
                    "function_name": function_name,
                },
                reason=f"Missing #include <{suggested_include}> for {reason_detail} in {file_path}",
                clue_source=clue
            )
        ]

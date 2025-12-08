"""
Planners for restoring missing C code (includes, functions).
"""

import os
import typing as T
from pipeline.planners.base import Planner
from pipeline.models import ErrorClue, RepairPlan, GitState
from pipeline.utils import is_verbose


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
        # ctype.h - Character classification
        "isdigit": "ctype.h", "isalpha": "ctype.h", "isalnum": "ctype.h", "isspace": "ctype.h",
        "islower": "ctype.h", "isupper": "ctype.h", "tolower": "ctype.h", "toupper": "ctype.h",
        # stdarg.h - Variable argument macros
         "va_start": "stdarg.h", "va_end": "stdarg.h", "va_list": "stdarg.h", "va_arg": "stdarg.h",
         # stdbool.h - Boolean type
         "bool": "stdbool.h", "true": "stdbool.h", "false": "stdbool.h",
         # stddef.h - Standard definitions
         "NULL": "stddef.h", "offsetof": "stddef.h",
         # stdint.h - Integer types
         "uint8_t": "stdint.h", "uint16_t": "stdint.h", "uint32_t": "stdint.h", "uint64_t": "stdint.h",
         "int8_t": "stdint.h", "int16_t": "stdint.h", "int32_t": "stdint.h", "int64_t": "stdint.h",
         "size_t": "stdint.h",
         # tree-sitter functions and constants - all come from api.h
         "ts_parser_new": "tree_sitter/api.h", "ts_parser_delete": "tree_sitter/api.h",
         "ts_parser_set_language": "tree_sitter/api.h", "ts_parser_parse_string": "tree_sitter/api.h",
         "ts_tree_root_node": "tree_sitter/api.h", "ts_tree_delete": "tree_sitter/api.h",
         "ts_query_new": "tree_sitter/api.h", "ts_query_delete": "tree_sitter/api.h",
         "ts_query_cursor_new": "tree_sitter/api.h", "ts_query_cursor_delete": "tree_sitter/api.h",
         "ts_query_cursor_exec": "tree_sitter/api.h", "ts_query_cursor_next_match": "tree_sitter/api.h",
         "ts_node_start_byte": "tree_sitter/api.h", "ts_node_end_byte": "tree_sitter/api.h",
         "TSQueryErrorSyntax": "tree_sitter/api.h",
         "TSQueryErrorNodeType": "tree_sitter/api.h",
         "TSQueryErrorField": "tree_sitter/api.h",
         "TSQueryErrorCapture": "tree_sitter/api.h",
         # time.h
         "time": "time.h", "time_t": "time.h",
        # ncurses.h / curses.h - Terminal UI library
        "initscr": "ncurses.h", "endwin": "ncurses.h", "refresh": "ncurses.h",
        "wrefresh": "ncurses.h", "getch": "ncurses.h", "wgetch": "ncurses.h",
        "printw": "ncurses.h", "wprintw": "ncurses.h", "mvprintw": "ncurses.h",
        "mvwprintw": "ncurses.h", "addch": "ncurses.h", "waddch": "ncurses.h",
        "addstr": "ncurses.h", "waddstr": "ncurses.h", "mvaddstr": "ncurses.h",
        "move": "ncurses.h", "wmove": "ncurses.h", "clear": "ncurses.h",
        "wclear": "ncurses.h", "erase": "ncurses.h", "werase": "ncurses.h",
        "clrtoeol": "ncurses.h", "wclrtoeol": "ncurses.h", "clrtobot": "ncurses.h",
        "raw": "ncurses.h", "noraw": "ncurses.h", "cbreak": "ncurses.h",
        "nocbreak": "ncurses.h", "echo": "ncurses.h", "noecho": "ncurses.h",
        "keypad": "ncurses.h", "nodelay": "ncurses.h", "timeout": "ncurses.h",
        "notimeout": "ncurses.h", "curs_set": "ncurses.h", "start_color": "ncurses.h",
        "init_pair": "ncurses.h", "attron": "ncurses.h", "attroff": "ncurses.h",
        "attrset": "ncurses.h", "getmaxx": "ncurses.h", "getmaxy": "ncurses.h",
        "getyx": "ncurses.h", "newwin": "ncurses.h", "delwin": "ncurses.h",
        "subwin": "ncurses.h", "derwin": "ncurses.h", "mvwin": "ncurses.h",
        "box": "ncurses.h", "border": "ncurses.h", "hline": "ncurses.h",
        "vline": "ncurses.h", "scrollok": "ncurses.h", "scroll": "ncurses.h",
        "scrl": "ncurses.h", "wscrl": "ncurses.h", "idlok": "ncurses.h",
        "stdscr": "ncurses.h", "curscr": "ncurses.h", "newscr": "ncurses.h",
        "LINES": "ncurses.h", "COLS": "ncurses.h", "TRUE": "ncurses.h",
        "FALSE": "ncurses.h", "ERR": "ncurses.h", "OK": "ncurses.h",
        "A_NORMAL": "ncurses.h", "A_STANDOUT": "ncurses.h", "A_UNDERLINE": "ncurses.h",
        "A_REVERSE": "ncurses.h", "A_BLINK": "ncurses.h", "A_DIM": "ncurses.h",
        "A_BOLD": "ncurses.h", "A_PROTECT": "ncurses.h", "A_INVIS": "ncurses.h",
        "A_ALTCHARSET": "ncurses.h", "COLOR_BLACK": "ncurses.h", "COLOR_RED": "ncurses.h",
        "COLOR_GREEN": "ncurses.h", "COLOR_YELLOW": "ncurses.h", "COLOR_BLUE": "ncurses.h",
        "COLOR_MAGENTA": "ncurses.h", "COLOR_CYAN": "ncurses.h", "COLOR_WHITE": "ncurses.h",
        "KEY_DOWN": "ncurses.h", "KEY_UP": "ncurses.h", "KEY_LEFT": "ncurses.h",
        "KEY_RIGHT": "ncurses.h", "KEY_HOME": "ncurses.h", "KEY_BACKSPACE": "ncurses.h",
        "KEY_F0": "ncurses.h", "KEY_DL": "ncurses.h", "KEY_IL": "ncurses.h",
        "KEY_DC": "ncurses.h", "KEY_IC": "ncurses.h", "KEY_EIC": "ncurses.h",
        "KEY_CLEAR": "ncurses.h", "KEY_EOS": "ncurses.h", "KEY_EOL": "ncurses.h",
        "KEY_SF": "ncurses.h", "KEY_SR": "ncurses.h", "KEY_NPAGE": "ncurses.h",
        "KEY_PPAGE": "ncurses.h", "KEY_STAB": "ncurses.h", "KEY_CTAB": "ncurses.h",
        "KEY_CATAB": "ncurses.h", "KEY_ENTER": "ncurses.h", "KEY_PRINT": "ncurses.h",
        "KEY_LL": "ncurses.h", "KEY_A1": "ncurses.h", "KEY_A3": "ncurses.h",
        "KEY_B2": "ncurses.h", "KEY_C1": "ncurses.h", "KEY_C3": "ncurses.h",
        "KEY_BTAB": "ncurses.h", "KEY_BEG": "ncurses.h", "KEY_CANCEL": "ncurses.h",
        "KEY_CLOSE": "ncurses.h", "KEY_COMMAND": "ncurses.h", "KEY_COPY": "ncurses.h",
        "KEY_CREATE": "ncurses.h", "KEY_END": "ncurses.h", "KEY_EXIT": "ncurses.h",
        "KEY_FIND": "ncurses.h", "KEY_HELP": "ncurses.h", "KEY_MARK": "ncurses.h",
        "KEY_MESSAGE": "ncurses.h", "KEY_MOVE": "ncurses.h", "KEY_NEXT": "ncurses.h",
        "KEY_OPEN": "ncurses.h", "KEY_OPTIONS": "ncurses.h", "KEY_PREVIOUS": "ncurses.h",
        "KEY_REDO": "ncurses.h", "KEY_REFERENCE": "ncurses.h", "KEY_REFRESH": "ncurses.h",
        "KEY_REPLACE": "ncurses.h", "KEY_RESTART": "ncurses.h", "KEY_RESUME": "ncurses.h",
        "KEY_SAVE": "ncurses.h", "KEY_SELECT": "ncurses.h", "KEY_SUSPEND": "ncurses.h",
        "KEY_UNDO": "ncurses.h", "KEY_MOUSE": "ncurses.h", "KEY_RESIZE": "ncurses.h",
        "KEY_EVENT": "ncurses.h",
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
            if is_verbose():
                print(f"[Planner:MissingCFunctionPlanner] Missing file_path or symbols")
            return []

        # Make path relative if it's absolute
        if os.path.isabs(file_path):
            file_path = os.path.relpath(file_path)

        # Only plan repairs for files that exist
        if not os.path.exists(file_path):
            if is_verbose():
                print(f"[Planner:MissingCFunctionPlanner] File {file_path} does not exist, skipping")
            return []

        # Separate stdlib symbols from user-defined symbols
        stdlib_symbols = [s for s in symbols if s in self.STDLIB_SYMBOL_TO_HEADER]
        user_symbols = [s for s in symbols if s not in self.STDLIB_SYMBOL_TO_HEADER]

        if stdlib_symbols and is_verbose():
            print(f"[Planner:MissingCFunctionPlanner] Found stdlib symbols needing includes: {stdlib_symbols}")
        if user_symbols and is_verbose():
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
                        if is_verbose():
                            print(f"[Planner:MissingCFunctionPlanner] Include <{header}> already present, skipping")
                        continue
            except Exception as e:
                if is_verbose():
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

        # For user-defined symbols, check if they might be macros/constants in local headers
        # before trying to restore them as functions
        macro_symbols = []
        function_symbols = []

        for symbol in user_symbols:
            # Check if symbol looks like a macro (all uppercase or starts with certain prefixes)
            if symbol.isupper() or symbol.startswith("KEY_"):
                # Try to find it in local headers
                header_file = self._find_header_for_macro(symbol, os.path.dirname(file_path) or ".")
                if header_file:
                    macro_symbols.append((symbol, header_file))
                    if is_verbose():
                        print(f"[Planner:MissingCFunctionPlanner] Found macro '{symbol}' in {header_file}")
                else:
                    # Couldn't find it in headers, treat as function
                    function_symbols.append(symbol)
            else:
                # Doesn't look like a macro, treat as function
                function_symbols.append(symbol)

        # Create include plans for macros
        headers_for_macros = {}
        for symbol, header in macro_symbols:
            if header not in headers_for_macros:
                headers_for_macros[header] = []
            headers_for_macros[header].append(symbol)

        for header, syms in headers_for_macros.items():
            # Check if the include is already present
            try:
                with open(file_path, 'r') as f:
                    content = f.read()
                    header_basename = os.path.basename(header)
                    if f'#include <{header_basename}>' in content or f'#include "{header_basename}"' in content:
                        if is_verbose():
                            print(f"[Planner:MissingCFunctionPlanner] Include for {header_basename} already present, skipping")
                        continue
            except Exception as e:
                if is_verbose():
                    print(f"[Planner:MissingCFunctionPlanner] Error reading {file_path}: {e}")
                continue

            plans.append(RepairPlan(
                plan_type="restore_c_code",
                priority=0,  # High priority - compilation error
                target_file=file_path,
                action="restore_c_element",
                params={
                    "ref": git_state.ref,
                    "element_name": os.path.basename(header),
                    "element_type": "include",
                },
                reason=f"Missing #include \"{header}\" for macros {', '.join(syms[:3])}{'...' if len(syms) > 3 else ''} in {file_path}",
                clue_source=clue
            ))

        # For function symbols, check if they're declared in a header first
        function_headers = {}
        functions_without_header = []

        for symbol in function_symbols:
            header = self._find_header_for_function(symbol, os.path.dirname(file_path) or ".")
            if header:
                if header not in function_headers:
                    function_headers[header] = []
                function_headers[header].append(symbol)
            else:
                # No header found, might need to restore the function itself
                functions_without_header.append(symbol)

        # Create include plans for functions that have headers
        for header, syms in function_headers.items():
            # Check if the include is already present
            include_present = False
            try:
                with open(file_path, 'r') as f:
                    content = f.read()
                    if f'#include <{header}>' in content or f'#include "{header}"' in content:
                        include_present = True
            except Exception as e:
                if is_verbose():
                    print(f"[Planner:MissingCFunctionPlanner] Error reading {file_path}: {e}")
                continue

            if include_present:
                # Include is present, so the functions should be in the header file
                # Create plans to restore each function to the header file
                src_dir = os.path.dirname(file_path)
                full_header_path = os.path.join(src_dir, header) if src_dir else header

                for func_name in syms:
                    plans.append(RepairPlan(
                        plan_type="restore_c_code",
                        priority=0,  # High priority - compilation error
                        target_file=full_header_path,
                        action="restore_c_element",
                        params={
                            "ref": git_state.ref,
                            "element_name": func_name,
                            "element_type": "function",
                        },
                        reason=f"Restore function '{func_name}' declaration to {header}",
                        clue_source=clue
                    ))
            else:
                # Include not present, add it to the source file
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
                    reason=f"Missing #include \"{header}\" for functions {', '.join(syms[:3])}{'...' if len(syms) > 3 else ''} in {file_path}",
                    clue_source=clue
                ))

        # Create function restoration plans for functions without headers
        for symbol in functions_without_header:
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

    def _find_header_for_macro(self, macro_name: str, start_dir: str) -> T.Optional[str]:
        """Find the header file that defines the given macro."""
        import subprocess

        # First try to search in git history (for deleted headers)
        try:
            result = subprocess.run(
                ["git", "grep", f"#define {macro_name}", "HEAD", "--", "*.h"],
                capture_output=True,
                text=True,
                timeout=2,
                cwd="."
            )
            if result.returncode == 0 and result.stdout.strip():
                # Parse output: HEAD:path/to/file.h:content
                for line in result.stdout.strip().split('\n'):
                    if ':' in line:
                        parts = line.split(':', 2)
                        if len(parts) >= 3:
                            # parts[0] = "HEAD", parts[1] = "path/to/file.h", parts[2] = code
                            header_path = parts[1]
                            header_name = os.path.basename(header_path)
                            return header_name
        except (subprocess.TimeoutExpired, Exception) as e:
            if is_verbose():
                print(f"[Planner:MissingCFunctionPlanner] Error searching git for macro: {e}")

        # Fallback: Search for #define macro_name in .h files on disk
        search_dirs = [start_dir, "."]

        for search_dir in search_dirs:
            if not os.path.exists(search_dir):
                continue

            try:
                # Search for #define macro_name
                result = subprocess.run(
                    ["grep", "-r", "-l", "--include=*.h", f"#define {macro_name}", search_dir],
                    capture_output=True,
                    text=True,
                    timeout=2
                )
                if result.returncode == 0 and result.stdout.strip():
                    headers = result.stdout.strip().split('\n')
                    # Return the first matching header
                    if headers:
                        return os.path.basename(headers[0])
            except (subprocess.TimeoutExpired, Exception) as e:
                if is_verbose():
                    print(f"[Planner:MissingCFunctionPlanner] Error searching for macro: {e}")
                continue

        return None

    def _find_header_for_function(self, function_name: str, start_dir: str) -> T.Optional[str]:
        """Find the header file that declares the given function."""
        import subprocess

        # Try to search in git history for function declarations
        # Look for patterns like: void function_name(...); or type function_name(...);
        try:
            result = subprocess.run(
                ["git", "grep", f"{function_name}(", "HEAD", "--", "*.h"],
                capture_output=True,
                text=True,
                timeout=2,
                cwd="."
            )
            if result.returncode == 0 and result.stdout.strip():
                # Parse output and look for function declarations (ending with ;)
                # Format is: HEAD:path/to/file.h:code
                for line in result.stdout.strip().split('\n'):
                    if ':' in line:
                        parts = line.split(':', 2)
                        if len(parts) >= 3:
                            # parts[0] = "HEAD", parts[1] = "path/to/file.h", parts[2] = code
                            header_path = parts[1]
                            code = parts[2].strip()
                            # Check if it's a declaration (ends with ;, not a definition with {)
                            if ';' in code and '{' not in code:
                                header_name = os.path.basename(header_path)
                                return header_name
        except (subprocess.TimeoutExpired, Exception) as e:
            if is_verbose():
                print(f"[Planner:MissingCFunctionPlanner] Error searching git for function: {e}")

        return None


class MissingCTypePlanner(Planner):
    """
    Plan fixes for missing C type definitions (unknown type name).

    Strategy:
    - When a type is unknown, find the local header that defines it
    - Search for typedef or struct definitions in project headers
    - Add the appropriate #include directive
    """

    @property
    def name(self) -> str:
        return "MissingCTypePlanner"

    def can_handle(self, clue_type: str) -> bool:
        return clue_type == "missing_c_type"

    def plan(self, clues: T.List[ErrorClue], git_state: GitState) -> T.List[RepairPlan]:
        plans = []
        for clue in clues:
            if clue.clue_type != "missing_c_type":
                continue
            plans.extend(self._plan_for_clue(clue, git_state))
        return plans

    def _plan_for_clue(self, clue: ErrorClue, git_state: GitState) -> T.List[RepairPlan]:
        file_path = clue.context.get("file_path")
        type_name = clue.context.get("type_name")

        if not file_path or not type_name:
            if is_verbose():
                print(f"[Planner:MissingCTypePlanner] Missing file_path or type_name")
            return []

        # Make path relative if it's absolute
        if os.path.isabs(file_path):
            file_path = os.path.relpath(file_path)

        # Only plan repairs for files that exist
        if not os.path.exists(file_path):
            if is_verbose():
                print(f"[Planner:MissingCTypePlanner] File {file_path} does not exist, skipping")
            return []

        # First, try to find which header file in the project defines this type
        # Look for .h files in the same directory and parent directories
        dir_path = os.path.dirname(file_path)
        if not dir_path:
            dir_path = "."

        # Try to find the header by searching for the type definition
        header_file = self._find_header_for_type(type_name, dir_path)

        if not header_file:
            if is_verbose():
                print(f"[Planner:MissingCTypePlanner] Could not find header defining type '{type_name}', skipping")
            return []

        # Check if the include is already present in the file
        include_present = False
        try:
            with open(file_path, 'r') as f:
                content = f.read()
                # Check for both <header.h> and "header.h" styles
                header_basename = os.path.basename(header_file)
                if f'#include <{header_basename}>' in content or f'#include "{header_basename}"' in content:
                    include_present = True
        except Exception as e:
            if is_verbose():
                print(f"[Planner:MissingCTypePlanner] Error reading {file_path}: {e}")
            return []

        # If include is present, the type should be in the header file
        # Create a plan to restore the type definition to the header file
        if include_present:
            # Determine the full path to the header file
            if '/' not in header_file:
                src_dir = os.path.dirname(file_path)
                full_header_path = os.path.join(src_dir, header_file) if src_dir else header_file
            else:
                full_header_path = header_file

            if is_verbose():
                print(f"[Planner:MissingCTypePlanner] Include present, restoring type '{type_name}' to {full_header_path}")

            return [
                RepairPlan(
                    plan_type="restore_c_code",
                    priority=0,  # High priority - compilation failure
                    target_file=full_header_path,
                    action="restore_c_element",
                    params={
                        "ref": git_state.ref,
                        "element_name": type_name,
                        "element_type": "type",
                    },
                    reason=f"Restore type '{type_name}' to {header_file}",
                    clue_source=clue
                )
            ]

        # Include is not present, add it to the source file
        if is_verbose():
            print(f"[Planner:MissingCTypePlanner] Planning to add '#include \"{header_file}\"' to {file_path}")

        return [
            RepairPlan(
                plan_type="restore_c_code",
                priority=0,  # High priority - compilation failure
                target_file=file_path,
                action="restore_c_element",
                params={
                    "ref": git_state.ref,
                    "element_name": os.path.basename(header_file),
                    "element_type": "include",
                    "type_name": type_name,
                },
                reason=f"Missing #include \"{header_file}\" for type '{type_name}' in {file_path}",
                clue_source=clue
            )
        ]

    def _find_header_for_type(self, type_name: str, start_dir: str) -> T.Optional[str]:
        """Find the header file that defines the given type."""
        import subprocess

        # Search for the type name in .h files
        # The type might be defined as:
        # - typedef struct foo { ... } foo_t;  (multiline)
        # - typedef ... foo_t;
        # - struct foo_t { ... };

        # First try to search in git history (for deleted headers)
        try:
            # Search git for .h files that contain the type definition
            result = subprocess.run(
                ["git", "grep", f"}} {type_name};", "HEAD", "--", "*.h"],
                capture_output=True,
                text=True,
                timeout=2,
                cwd="."
            )
            if result.returncode == 0 and result.stdout.strip():
                # Parse output: HEAD:path/to/file.h:content
                for line in result.stdout.strip().split('\n'):
                    if ':' in line:
                        parts = line.split(':', 2)
                        if len(parts) >= 3:
                            # parts[0] = "HEAD", parts[1] = "path/to/file.h", parts[2] = code
                            header_path = parts[1]
                            header_name = os.path.basename(header_path)
                            return header_name
        except (subprocess.TimeoutExpired, Exception) as e:
            if is_verbose():
                print(f"[Planner:MissingCTypePlanner] Error searching git for type: {e}")

        # Also try searching for typedef patterns
        try:
            result = subprocess.run(
                ["git", "grep", f"typedef.*{type_name}", "HEAD", "--", "*.h"],
                capture_output=True,
                text=True,
                timeout=2,
                cwd="."
            )
            if result.returncode == 0 and result.stdout.strip():
                for line in result.stdout.strip().split('\n'):
                    if ':' in line:
                        parts = line.split(':', 2)
                        if len(parts) >= 3:
                            # parts[0] = "HEAD", parts[1] = "path/to/file.h", parts[2] = code
                            header_path = parts[1]
                            header_name = os.path.basename(header_path)
                            return header_name
        except (subprocess.TimeoutExpired, Exception) as e:
            if is_verbose():
                print(f"[Planner:MissingCTypePlanner] Error searching git for typedef: {e}")

        # Fallback: Search in current directory and common include paths
        search_dirs = [start_dir, "."]

        for search_dir in search_dirs:
            if not os.path.exists(search_dir):
                continue

            try:
                # First try to find files containing the type name
                result = subprocess.run(
                    ["grep", "-r", "-l", "--include=*.h", type_name, search_dir],
                    capture_output=True,
                    text=True,
                    timeout=2
                )
                if result.returncode == 0 and result.stdout.strip():
                    headers = result.stdout.strip().split('\n')

                    # Verify each header actually defines the type (not just uses it)
                    for header in headers:
                        try:
                            with open(header, 'r') as f:
                                content = f.read()
                                # Check if this header defines the type
                                # Look for typedef ending with type_name; or struct type_name
                                if (f'}} {type_name};' in content or
                                    f'typedef struct {type_name}' in content or
                                    f'struct {type_name} {{' in content):
                                    # Found the definition
                                    if is_verbose():
                                        print(f"[Planner:MissingCTypePlanner] Found type '{type_name}' defined in {header}")
                                    return os.path.basename(header)
                        except Exception as e:
                            if is_verbose():
                                print(f"[Planner:MissingCTypePlanner] Error reading {header}: {e}")
                            continue

                    # If no exact match found, try name-based heuristics
                    for header in headers:
                        header_base = os.path.basename(header).replace('.h', '')
                        # Remove common suffixes like _t to match base name
                        type_base = type_name.replace('_t', '')
                        if header_base == type_base or header_base in type_base or type_base in header_base:
                            if is_verbose():
                                print(f"[Planner:MissingCTypePlanner] Using name heuristic: {type_name} likely in {header}")
                            return os.path.basename(header)

                    # If still nothing, return the first one
                    if headers:
                        if is_verbose():
                            print(f"[Planner:MissingCTypePlanner] Guessing first match: {headers[0]}")
                        return os.path.basename(headers[0])

            except (subprocess.TimeoutExpired, Exception) as e:
                if is_verbose():
                    print(f"[Planner:MissingCTypePlanner] Error searching for type: {e}")
                continue

        return None


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
            if is_verbose():
                print(f"[Planner:MissingCIncludePlanner] Missing file_path")
            return []

        # Make path relative if it's absolute
        if os.path.isabs(file_path):
            file_path = os.path.relpath(file_path)

        # Only plan repairs for files that exist
        if not os.path.exists(file_path):
            if is_verbose():
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
            # tree-sitter types - all come from api.h
            "TSLanguage": "tree_sitter/api.h",
            "TSNode": "tree_sitter/api.h",
            "TSParser": "tree_sitter/api.h",
            "TSTree": "tree_sitter/api.h",
            "TSQuery": "tree_sitter/api.h",
            "TSQueryError": "tree_sitter/api.h",
            "TSQueryCursor": "tree_sitter/api.h",
            "TSQueryMatch": "tree_sitter/api.h",
            "TSQueryCapture": "tree_sitter/api.h",
        }

        # If we have a suggested include, use it; otherwise try to map from struct name
        if not suggested_include:
            if struct_name and struct_name in STRUCT_TO_HEADER:
                suggested_include = STRUCT_TO_HEADER[struct_name]
                if is_verbose():
                    print(f"[Planner:MissingCIncludePlanner] Mapped struct '{struct_name}' to header '{suggested_include}'")
            else:
                if is_verbose():
                    print(f"[Planner:MissingCIncludePlanner] No suggested include and can't map struct '{struct_name}', skipping")
                return []

        # Check if the include is already present in the file
        try:
            with open(file_path, 'r') as f:
                content = f.read()
                # Check for both <header.h> and "header.h" styles
                # Also check basename to handle paths like tree_sitter/api.h
                header_basename = os.path.basename(suggested_include)
                if f'#include <{suggested_include}>' in content or f'#include "{suggested_include}"' in content or \
                   f'#include <{header_basename}>' in content or f'#include "{header_basename}"' in content:
                    if is_verbose():
                        print(f"[Planner:MissingCIncludePlanner] Include <{suggested_include}> already present in {file_path}, skipping")
                    return []
        except Exception as e:
            if is_verbose():
                print(f"[Planner:MissingCIncludePlanner] Error reading {file_path}: {e}")
            return []

        reason_detail = f"function '{function_name}'" if function_name else f"struct '{struct_name}'"
        if is_verbose():
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

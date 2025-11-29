import os
import re
import subprocess
import typing as T

import src_repair
from session import ctx

def run_command(command: T.List[str]) -> T.Tuple[str, str, int]:
    """
    Run a shell command and return its output, error and exit code.

    Returns standard Unix exit codes:
    - 126: Permission denied
    - 127: Command not found
    """
    print(f"Running: {' '.join(command)}")
    try:
        result = subprocess.run(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        return result.stdout, result.stderr, result.returncode
    except FileNotFoundError as e:
        # Return exit code 127 (standard for "command not found")
        return "", f"FileNotFoundError: {e}", 127
    except PermissionError as e:
        # Return exit code 126 (standard for "permission denied")
        return "", f"PermissionError: {e}", 126

def git_checkout(file_path: str, ref: str = "HEAD") -> bool:
    """Run git checkout for the given file path.
    
    file_path should be relative to the git root (as returned by git diff).
    """
    deleted_files = set(get_deleted_files(ref=ref))
    if file_path not in deleted_files:
        print(f"missing: {file_path}")
        return False

    # Convert git-root-relative path to cwd-relative path for file operations
    git_toplevel = get_git_toplevel()
    cwd = os.getcwd()
    abs_path = os.path.join(git_toplevel, file_path)
    cwd_relative_path = os.path.relpath(abs_path, cwd)

    # For Python files, create empty file first and let src_repair handle restoration
    if file_path.endswith(".py"):
        print(f"creating empty Python file: {cwd_relative_path}")
        # Create parent directories if needed
        os.makedirs(os.path.dirname(cwd_relative_path) or ".", exist_ok=True)
        # Create empty Python file
        with open(cwd_relative_path, 'w') as f:
            f.write("")
        return True

    # For non-Python files, do full checkout from git root
    command = ["git", "-C", git_toplevel, "checkout", ref, "--", file_path]
    stdout, stderr, code = run_command(command)
    if code != 0:
        print("stdout:", stdout)
        print("stderr:", stderr)
        raise ValueError(file_path)
    success = os.path.exists(cwd_relative_path)
    print(f"success = {success}")
    return success


def get_python_file_path(module_name: str) -> str:
    """Convert a Python module name to a file path."""
    return module_name.replace(".", "/") + ".py"


def get_python_init_path(module_name: str) -> str:
    """Convert a Python module name to a __init__.py path."""
    return module_name.replace(".", "/") + "/__init__.py"


def get_git_toplevel() -> str:
    """Get the git repository root directory."""
    return subprocess.check_output(
        ["git", "rev-parse", "--show-toplevel"], text=True
    ).strip()


def get_deleted_files(ref: str = "HEAD") -> T.Set[str]:
    """Get the list of deleted files from `git status`."""
    # Fallback: use the working directory state
    result = subprocess.run(
        ["git", "diff", "--name-status"], stdout=subprocess.PIPE, text=True
    )
    # TODO: what if result fails?
    return set(
        line.split()[-1] for line in result.stdout.splitlines() if line.startswith("D")
    )


def restore_missing_file(missing_file: str, ref: T.Optional[str] = None) -> bool:
    """
    Restore a missing_file to disk, inferring the file path based on git diff since provided ref.
    """
    print(f"Restoring missing file {missing_file}")
    ref = ref or ctx().git_ref
    
    # Get git toplevel to compute paths relative to repo root
    git_toplevel = get_git_toplevel()
    cwd = os.getcwd()
    
    # Convert the file path to be relative to git root (not cwd)
    # First resolve relative to cwd, then make relative to git root
    abs_path = os.path.abspath(missing_file)
    relative_path = os.path.relpath(abs_path, git_toplevel)
    
    # Also compute the cwd-relative path from git_toplevel
    cwd_relative_to_git = os.path.relpath(cwd, git_toplevel)
    
    deleted_files = get_deleted_files(ref=ref)

    if relative_path in deleted_files:
        if git_checkout(relative_path, ref=ref):
            return True
        print(f"Did not restore {relative_path}, looking for alternatives")
    else:
        print(f"{relative_path} is not deleted, looking for alternatives")

    # Attempt to match the missing module path to a deleted file
    matching_files = [f for f in deleted_files if relative_path in f]

    if matching_files:
        for path in matching_files:
            print(f"Found matching path for {relative_path}: {path}")
            if git_checkout(path):
                return True
    print(f"Could not find a matching path for {relative_path}")

    # try and find a match on the filename
    filename = os.path.basename(relative_path)
    print(f"Searching for ANY file named {filename}")
    matching_files = [f for f in deleted_files if filename in f]

    if matching_files:
        for path in matching_files:
            print(f"Found matching file for {filename}: {path}")
            if git_checkout(path):
                return True

    print(f"Failed to restore {missing_file}. Maybe its a directory?")

    # maybe it's a directory? check
    dirname = filename + "/"
    matching_dirs = [f for f in deleted_files if dirname in f]
    if matching_dirs:
        print(f"Found {len(matching_dirs)} files in directory {dirname}")
        # Try to restore all files in the directory
        success_count = 0
        for file_path in matching_dirs:
            print(f"Attempting to restore: {file_path}")
            if git_checkout(file_path, ref=ref):
                success_count += 1
        if success_count > 0:
            print(f"Successfully restored {success_count}/{len(matching_dirs)} files from {dirname}")
            return True
    
    # Try a broader directory search pattern
    dir_base = os.path.basename(relative_path)
    print(f"Searching for directory pattern: {dir_base}/")
    broad_matching_dirs = [f for f in deleted_files if f"/{dir_base}/" in f or f.startswith(f"{dir_base}/")]
    if broad_matching_dirs:
        print(f"Found {len(broad_matching_dirs)} files in broader directory search for {dir_base}")
        success_count = 0
        for file_path in broad_matching_dirs:
            print(f"Attempting to restore: {file_path}")
            if git_checkout(file_path, ref=ref):
                success_count += 1
        if success_count > 0:
            print(f"Successfully restored {success_count}/{len(broad_matching_dirs)} files from {dir_base} pattern")
            return True
    
    # If we're in a subdirectory, try prefixing the relative path with the subdirectory name
    # This handles the case where error messages report filenames without directory prefixes
    # but the git diff shows them with the subdirectory prefix
    if cwd_relative_to_git != ".":
        # Only add the prefix if relative_path doesn't already start with it
        if not relative_path.startswith(cwd_relative_to_git):
            subdir_prefixed = os.path.join(cwd_relative_to_git, relative_path)
            print(f"Trying with subdirectory prefix: {subdir_prefixed}")
            
            if subdir_prefixed in deleted_files:
                if git_checkout(subdir_prefixed, ref=ref):
                    return True
            
            # Also try matching with this prefixed path
            matching_files = [f for f in deleted_files if subdir_prefixed in f]
            if matching_files:
                for path in matching_files:
                    print(f"Found matching path with subdirectory prefix: {path}")
                    if git_checkout(path):
                        return True
    
    return False


def handle_shell_command_not_found(stderr: str) -> bool:
    """Handle shell errors when a command/script is not found.
    
    Example errors:
        ./test.sh: 2: ./configure: not found
        /bin/sh: ./script.sh: not found
        ./test.sh: line 3: ./configure: No such file or directory
    """
    # Pattern 1: line_num: ./command: not found
    pattern = r":\s*\d+:\s*([^\s:]+):\s*not found"
    match = re.search(pattern, stderr)
    
    # Pattern 2: line N: ./command: No such file or directory
    if not match:
        pattern = r": line \d+:\s*([^\s:]+):\s*No such file or directory"
        match = re.search(pattern, stderr)
    
    if not match:
        return False
    
    missing_cmd = match.group(1).strip()
    print(f"Shell command not found: {missing_cmd}")
    
    # Remove ./ prefix if present for file lookup
    if missing_cmd.startswith("./"):
        missing_cmd = missing_cmd[2:]
    
    return restore_missing_file(missing_cmd)


def handle_cat_no_such_file(stderr: str) -> bool:
    """Handle cat errors when a file is missing.
    
    Example error:
        cat: Makefile.in: No such file or directory
    """
    pattern = r"cat:\s*([^\s:]+):\s*No such file or directory"
    match = re.search(pattern, stderr)
    
    if not match:
        return False
    
    missing_file = match.group(1).strip()
    print(f"cat: missing file: {missing_file}")
    
    return restore_missing_file(missing_file)


def handle_diff_no_such_file(stderr: str) -> bool:
    """Handle diff errors when a file is missing.
    
    Example error:
        diff: test.txt: No such file or directory
    """
    pattern = r"diff:\s*([^\s:]+):\s*No such file or directory"
    match = re.search(pattern, stderr)
    
    if not match:
        return False
    
    missing_file = match.group(1).strip()
    print(f"diff: missing file: {missing_file}")
    
    return restore_missing_file(missing_file)


def handle_sh_cannot_open(stderr: str) -> bool:
    """Handle sh errors when a file cannot be opened.
    
    Example error:
        sh: 0: cannot open makeoptions: No such file
    """
    pattern = r"sh:\s*\d+:\s*cannot open\s+([^\s:]+):\s*No such file"
    match = re.search(pattern, stderr)
    
    if not match:
        return False
    
    missing_file = match.group(1).strip()
    print(f"sh: cannot open: {missing_file}")
    
    return restore_missing_file(missing_file)


def handle_sh_cant_cd(stderr: str) -> bool:
    """Handle sh errors when cd fails because directory doesn't exist.
    
    Example error:
        /bin/sh: 1: cd: can't cd to libuxre
    """
    pattern = r"cd: can't cd to\s+([^\s]+)"
    match = re.search(pattern, stderr)
    
    if not match:
        return False
    
    missing_dir = match.group(1).strip()
    print(f"sh: can't cd to: {missing_dir}")
    
    # Restore all files in that directory
    return restore_missing_file(missing_dir)


def handle_no_such_file_or_directory(stderr: str) -> bool:
    """Handle the case where a missing executable or file is reported."""
    match = re.search(r"([^\s]+): (\[Errno \d\])? No such file or directory", stderr)

    if not match:
        print("failed to match")
        return False
    print(match)
    missing_file = match.group(1).strip()
    print(f"Missing file or executable: {missing_file}")

    # Attempt to `git checkout` the missing file or directory
    return restore_missing_file(missing_file)


def parse_traceback(traceback_text: str) -> T.Tuple[T.Optional[str], T.Optional[str]]:
    """
    Look for NameErrors in a python traceback and return (file, name).
    """
    # Regular expression to find the file path and line number
    file_line_regex = re.compile(r'  File "(?P<file>.*?)", line (?P<line>\d+), in ')

    # Regular expression to find the NameError and the undefined name
    name_error_regex = re.compile(
        r"NameError: (?:global )?name '(?P<name>\w+)' is not defined"
    )

    # Initialize variables
    last_file = None

    # Split traceback text into lines
    lines = traceback_text.splitlines()

    for line in lines:
        # Match file and line number
        file_match = file_line_regex.match(line)
        if file_match:
            last_file = file_match.group("file")

        # Match NameError
        name_error_match = name_error_regex.match(line)
        if name_error_match and last_file:
            undefined_name = name_error_match.group("name")
            return last_file, undefined_name

    # If no NameError was found, return None
    return None, None


def parse_import_error(error_message: str) -> T.Tuple[T.Optional[str], T.Optional[str]]:
    """
    Read a traceback and look for import errors, return (file, import name).
    """
    # Regular expression to find the import error details
    import_error_regex = re.compile(
        r"ImportError: cannot import name '(?P<name>\w+)' from '(?P<module>[\w\.]+)' \((?P<file>.*?)\)"
    )

    # Match the error message
    match = import_error_regex.search(error_message)

    if match:
        name = match.group("name")
        file = match.group("file")
        if file == "unknown location":
            return None, None
        return file, name

    # If no match is found, return None
    return None, None




def handle_future_annotations(stderr: str) -> bool:
    """
    Fix a NameError caused by forward reference in type annotations.
    This happens when a class name is used in a type annotation before the class is defined,
    and 'from __future__ import annotations' is missing.
    """
    # Parse the NameError to get filepath and name
    filepath, name = parse_traceback(stderr)
    if filepath is None:
        return False
    
    # Check if this looks like a forward reference issue
    # Look for patterns where the name appears in type annotations:
    # - dict[tuple, ClassName] = {}
    # - dict[weakref.ref[ClassName], None] = {}
    # - other_type[ClassName] = {}
    # We look for the name appearing after a comma, inside brackets, or at start of brackets
    type_annotation_patterns = [
        rf"\[.*,\s*{re.escape(name)}\]",  # dict[tuple, DType]
        rf"\[{re.escape(name)}\]",       # list[DType] 
        rf"\[.*{re.escape(name)}.*\]",   # any bracket containing the name
    ]
    
    if not any(re.search(pattern, stderr) for pattern in type_annotation_patterns):
        return False
    
    relative_path = os.path.relpath(filepath)
    print(f"repairing {relative_path} for future annotations (forward reference {name=})")
    return do_repair(relative_path, missing="annotations")


def handle_orphaned_method(stderr: str) -> bool:
    """
    Handle IndentationError caused by a method missing its class definition.
    This happens when a class definition is deleted but the methods remain.

    Example:
        class Dog:  # <- This line deleted
            def __init__(self, name):  # <- IndentationError: unexpected indent
                self.name = name
    """
    # Look for "unexpected indent" pattern
    if "IndentationError: unexpected indent" not in stderr:
        return False

    # Find the file and line number where the error occurred
    file_lines = [line for line in stderr.split('\n') if 'File "' in line]
    if not file_lines:
        return False

    last_file_line = file_lines[-1]
    file_match = re.search(r'File "([^"]+)", line (\d+)', last_file_line)
    if not file_match:
        return False

    filepath = file_match.group(1)
    error_line_num = int(file_match.group(2))
    relative_path = os.path.relpath(filepath)

    # Read the file to see what's on the problematic line
    try:
        with open(filepath, 'r') as f:
            lines = f.readlines()
            if error_line_num <= len(lines):
                error_line = lines[error_line_num - 1]

                # Check if it's a method definition (def with leading whitespace)
                if re.match(r'\s+def\s+(\w+)', error_line):
                    print(f"Detected orphaned method on line {error_line_num}: {error_line.strip()}")
                    print(f"Attempting to restore missing class definition in {relative_path}")

                    # Try to restore the file with src_repair without specifying a missing item
                    # This should restore the class that contains this method
                    # We'll use the method name to help identify what needs restoring
                    method_match = re.match(r'\s+def\s+(\w+)', error_line)
                    if method_match:
                        method_name = method_match.group(1)
                        # Try restoring with the method name - src_repair should restore
                        # the entire class context needed for this method
                        print(f"Restoring context for method: {method_name}")
                        return do_repair(relative_path, missing=method_name)
    except (IOError, IndexError) as e:
        print(f"Error reading file: {e}")
        return False

    return False


def handle_indentation_error(stderr: str) -> bool:
    """
    Fix IndentationError by restoring missing imports or code blocks.
    Common cases: 
    1. 'if TYPE_CHECKING:' block missing its indented imports
    2. Method definitions without containing class
    3. Any other structural indentation issues
    """
    # Look for IndentationError patterns
    indentation_match = re.search(r"IndentationError: (expected an indented block after '(.+)' statement on line (\d+)|unexpected indent)", stderr)
    if not indentation_match:
        return False
    
    # Use the same traceback parsing logic as other handlers
    # Find the last file mentioned before the IndentationError
    file_lines = [line for line in stderr.split('\n') if 'File "' in line]
    if not file_lines:
        return False
    
    # Get the last file path (where the error actually occurred)
    last_file_line = file_lines[-1]
    file_match = re.search(r'File "([^"]+)"', last_file_line)
    if not file_match:
        return False
    
    filepath = file_match.group(1)
    relative_path = os.path.relpath(filepath)
    
    # Parse the type of indentation error
    if "unexpected indent" in stderr:
        print(f"repairing {relative_path} for unexpected indent - likely broken class structure")
        # File structure is too broken, restore the whole file
        try:
            subprocess.check_call(["git", "checkout", "HEAD", "--", relative_path])
            print(f"Successfully restored {relative_path} from HEAD")
            return True
        except subprocess.CalledProcessError:
            print(f"Failed to restore {relative_path} from HEAD")
            return False
    
    # Handle "expected an indented block" errors
    statement = indentation_match.group(2) if indentation_match.group(2) else ""
    line_num = int(indentation_match.group(3)) if indentation_match.group(3) else 0
    print(f"repairing {relative_path} for indentation error after '{statement}' on line {line_num}")
    
    # For TYPE_CHECKING blocks, try to restore the missing imports
    if statement == "if":
        # Read the file to check if it's a TYPE_CHECKING block
        try:
            with open(filepath, 'r') as f:
                lines = f.readlines()
                if line_num <= len(lines) and "TYPE_CHECKING" in lines[line_num - 1]:
                    print(f"Detected TYPE_CHECKING block issue, attempting full file restoration")
                    # The file is too broken to repair incrementally, restore the whole file
                    try:
                        subprocess.check_call(["git", "checkout", "HEAD", "--", relative_path])
                        print(f"Successfully restored {relative_path} from HEAD")
                        return True
                    except subprocess.CalledProcessError:
                        print(f"Failed to restore {relative_path} from HEAD")
                        return False
        except (IOError, IndexError):
            pass
    
    # For any other indentation error, try full file restoration first
    # since partial repairs often leave files in broken states
    try:
        subprocess.check_call(["git", "checkout", "HEAD", "--", relative_path])
        print(f"Successfully restored {relative_path} from HEAD for general indentation error")
        return True
    except subprocess.CalledProcessError:
        print(f"Failed to restore {relative_path} from HEAD, trying partial repair")
        # Fallback to general repair attempt
        return do_repair(relative_path)


def handle_import_error2(stderr: str) -> bool:
    # regex to find the filename and the name causing the NameError
    filepath, import_name = parse_import_error(stderr)
    if filepath is None:
        return False

    relative_path = os.path.relpath(filepath)
    print(f"repairing {relative_path} for {import_name=}")
    return do_repair(relative_path, missing=import_name)


def handle_module_attribute_error(err: str) -> bool:
    # Match the stack trace pattern to check for AttributeError
    match = re.search(r"AttributeError: module '(.*)' has no attribute '(\w+)'", err)

    if not match:
        print("no module attribute match")
        return False

    # Extract the class name and missing method from the error message
    module_name, missing_method = match.groups()

    module_path = module_name.replace(".", "/") + ".py"

    # Call the repair tool to restore the missing method
    print(f"repairing {module_path=} for {missing_method=}")
    return do_repair(module_path, missing_method)

def handle_object_attribute_error(err: str) -> bool:
    # Match the stack trace pattern to check for AttributeError
    match = re.search(r"AttributeError: '(\w+)' object has no attribute '(\w+)'", err)

    if not match:
        print("no object attribute match")
        return False

    # Extract the class name and missing method from the error message
    class_name, missing_method = match.groups()

    # Use git grep to locate the file that defines the class
    try:
        grep_output = subprocess.check_output(
            ["git", "grep", f"class {class_name}"], text=True
        )
    except subprocess.CalledProcessError:
        # If git grep fails to find the class, return False
        return False

    # Extract the file path from the grep output
    file_path = grep_output.split(":")[0]

    # Call the repair tool to restore the missing method
    print(f"repairing {file_path} for {missing_method=}")
    return do_repair(file_path, missing_method)


def handle_missing_pyc(stderr: str) -> bool:
    """Handle the case where bash complains that a Python file is missing."""
    missing_file_error_pattern = re.compile(r"can't open file '(.+\.pyc)'")
    match = missing_file_error_pattern.search(stderr)
    if not match:
        return False
    missing_file = match.group(1).replace(".pyc", ".py")  # Convert .pyc to .py
    print(f"Missing file: {missing_file}")
    return restore_missing_file(missing_file)


def handle_missing_file(stderr: str) -> bool:
    """Handle the case where bash complains that a Python file is missing."""
    missing_file_error_pattern = re.compile(r"can't open file '(.+)'")
    match = missing_file_error_pattern.search(stderr)
    if not match:
        return False
    missing_file = match.group(1)
    print(f"Missing file: {missing_file}")
    return restore_missing_file(missing_file)


def handle_missing_py_package(stderr: str) -> bool:
    """Handle the case where a Python import fails due to a missing module or file."""
    combined_error_pattern = re.compile(
        r"File .*line \d+, in <module>\s+from (.*) import .*[\r\n]+ModuleNotFoundError: No module named '(.*)'"
    )

    match = combined_error_pattern.search(stderr)

    if not match:
        return False
    # Extract the actual import path and the missing module from the combined error pattern
    actual_import = match.group(1)
    missing_module = match.group(2)
    print(f"Actual import causing the error: {actual_import}")

    # Now we can work with the full import path to figure out the correct file to restore
    module_path = actual_import.replace(".", "/")

    # Attempt to `git checkout` the missing file or directory
    if restore_missing_file(module_path):
        return True

    print(f"Could not restore the missing module: {actual_import}")
    return False


def handle_file_not_found(stderr: str) -> bool:
    # Search for missing module/file paths in the error output
    # Match patterns like: FileNotFoundError: [Errno 2] No such file or directory: '/path/to/file'
    file_not_found_pattern = re.compile(r"FileNotFoundError:.*?No such file or directory: '([^']+)'")
    match = file_not_found_pattern.search(stderr)
    if not match:
        # Fallback to simpler pattern
        simple_pattern = re.compile(r"FileNotFoundError: (.*)")
        simple_match = simple_pattern.search(stderr)
        if not simple_match:
            return False
        missing_file = simple_match.group(1)
    else:
        missing_file = match.group(1)
    
    print(f"Extracted missing file: {missing_file}")
    return restore_missing_file(missing_file)


def handle_missing_py_module(stderr: str) -> bool:
    # Search for missing module/file paths in the error output
    missing_module_error_pattern = re.compile(r"No module named '?(.*)'?")
    match = missing_module_error_pattern.search(stderr)
    if not match:
        return False
    missing_module = match.group(1).rstrip("'")
    print(f"Missing module: {missing_module}")

    # Convert the module name to a file path and checkout the file
    file_path = get_python_file_path(missing_module)
    if restore_missing_file(file_path):
        # successfully restore, try again
        return True
    # git checkout didn't work. Try a folder instead?
    init_path = get_python_init_path(missing_module)
    if restore_missing_file(init_path):
        return True

    # Not sure what this could be.
    # Imports outside aircam maybe?
    print(f"Failed to restore {missing_module}")
    return False


def handle_import_error1(stderr: str) -> bool:
    """Handle the case where a Python import fails, including cases where a name cannot be imported."""
    # Match the error where the import fails due to a missing name in the module
    match = re.search(
        r"ImportError: cannot import name '(.*)' from '(.*)' \((.*)\)", stderr
    )
    if not match:
        return False
    missing_name = match.group(1)
    module_path = match.group(2)
    location = match.group(3)

    print(
        f"Missing import: {missing_name} from module: {module_path} at location: {location}"
    )

    # Construct the expected file path based on the module path and the missing name
    if location.endswith("__init__.py"):
        # The error is from an __init__.py file, likely due to a missing file in the same module
        file_path = os.path.join(os.path.dirname(location), f"{missing_name}.py")
    else:
        # This should not happen, but if it does, fallback to the standard module path resolution
        file_path = os.path.join(module_path.replace(".", "/"), f"{missing_name}.py")

    print(f"Attempting to restore: {file_path}")

    # Attempt to git checkout the missing file
    return restore_missing_file(file_path)


def handle_circular_import_error(err: str) -> bool:
    """Handle circular import errors by restoring the missing module file."""
    # Match pattern: ImportError: cannot import name 'optim' from partially initialized module 'tinygrad.nn' (most likely due to a circular import)
    circular_import_pattern = re.compile(
        r"ImportError: cannot import name '(\w+)' from partially initialized module '([^']+)' \(most likely due to a circular import\)"
    )
    match = circular_import_pattern.search(err)
    if not match:
        return False
    
    missing_name = match.group(1)
    module_path = match.group(2)
    
    print(f"Detected circular import: missing '{missing_name}' from '{module_path}'")
    
    # Try to restore the missing submodule file
    # For 'optim' from 'tinygrad.nn', try 'tinygrad/nn/optim.py'
    submodule_path = module_path.replace(".", "/") + "/" + missing_name + ".py"
    print(f"Attempting to restore submodule: {submodule_path}")
    
    if restore_missing_file(submodule_path):
        return True
    
    # Fallback: try to restore missing item from the main module file
    main_module_path = module_path.replace(".", "/") + ".py"
    print(f"Fallback: repairing main module {main_module_path} for {missing_name}")
    return do_repair(main_module_path, missing_name)


def handle_import_name_error(err: str) -> bool:
    # Handle ImportError pattern
    import_error_match = re.search(r"ImportError: cannot import name '?(\w+)'?", err)
    if not import_error_match:
        return False

    missing_function = import_error_match.group(1)

    # Extract the file path from the import statement in the traceback
    file_path_match = re.search(r"from (.+) import", err)
    if not file_path_match:
        return False
    module_path = file_path_match.group(1).replace(".", "/") + ".py"
    print(f"repairing {module_path} for {missing_function=}")
    if do_repair(module_path, missing_function):
        return True
    # fail to work. possibly we guessed wrong. Lets assume a package
    package_path = (
        file_path_match.group(1).replace(".", "/") + "/" + missing_function + ".py"
    )
    return do_repair(package_path)


def do_repair(
    file_path: str, missing: T.Optional[str] = None, ref: T.Optional[str] = None
) -> bool:
    print(f"repair --missing {missing} {file_path}")
    try:
        src_repair.repair(
            filename=file_path,
            commit=ref or ctx().git_ref,
            missing=missing,
            verbose=False,
        )
        return True
    except Exception as e:
        print(f"failed to repair {file_path} with {missing=}: {e}")
        return False


def handle_permission_denied(err: str) -> bool:
    """Handle the case where a file exists but doesn't have execute permissions."""
    # Check for PermissionError prefix (from run_command exception)
    # or standard "Permission denied" message
    if "PermissionError:" not in err and "Permission denied" not in err:
        return False

    # Extract the file path from the error message
    # Formats:
    #   PermissionError: [Errno 13] Permission denied: './test_tree_print.py'
    #   Permission denied: './test_tree_print.py'
    #   /bin/sh: 1: ./testty.py: Permission denied
    match = re.search(r"Permission denied:\s*['\"]?([^'\"]+)['\"]?", err)
    if not match:
        # Try the /bin/sh format: "path: Permission denied"
        match = re.search(r":\s*([^\s:]+):\s*Permission denied", err)
    
    if not match:
        print("Could not extract file path from permission error")
        return False

    file_path = match.group(1).strip()
    print(f"Permission denied for: {file_path}")

    # If this is a modified file (not deleted), restore it from git
    # to get the correct permissions
    relative_path = os.path.relpath(file_path) if os.path.isabs(file_path) else file_path

    # Check if the file exists
    if not os.path.exists(relative_path):
        print(f"File {relative_path} does not exist, trying to restore")
        return restore_missing_file(relative_path)

    # File exists but has wrong permissions - restore from git
    print(f"File exists but has wrong permissions, restoring from git")
    try:
        git_toplevel = get_git_toplevel()
        cwd = os.getcwd()
        
        # Convert relative path to git-root-relative path for git checkout
        abs_path = os.path.abspath(relative_path)
        git_relative_path = os.path.relpath(abs_path, git_toplevel)
        
        subprocess.check_call(["git", "-C", git_toplevel, "checkout", "HEAD", "--", git_relative_path])
        print(f"Successfully restored {relative_path} with correct permissions from git")
        return True
    except subprocess.CalledProcessError:
        print(f"Failed to restore {relative_path} from git")
        return False


def handle_executable_not_found(err: str) -> bool:
    """Handle the case where the executable is missing."""
    # Check for FileNotFoundError prefix (from run_command exception)
    # or standard "No such file or directory" message
    if "FileNotFoundError:" not in err and "No such file or directory" not in err:
        return False

    # Try to extract file path from FileNotFoundError format first
    # Format: FileNotFoundError: [Errno 2] No such file or directory: './test.py'
    file_match = re.search(r"FileNotFoundError:.*?['\"]([^'\"]+)['\"]", err)
    if file_match:
        missing_executable = file_match.group(1)
    else:
        # Fallback to old parsing
        if "No such file or directory" not in err:
            return False
        missing_executable = err.split(":")[-1].strip().strip("'")

    print(f"Missing executable: {missing_executable}")

    # Handle paths with spaces by checking if it looks like a reasonable file path
    # Only reject if it contains multiple unrelated components or shell commands
    if " " in missing_executable and not missing_executable.startswith(("/", "./")):
        # Looks like multiple shell arguments rather than a single path
        return False

    # Check if the executable path is relative and if it's a symlink
    if missing_executable.startswith("./"):
        relative_path = missing_executable[2:]  # Remove './' from the start
    else:
        relative_path = missing_executable

    # Check if the path is supposed to be a symlink
    if os.path.islink(relative_path):
        target = os.readlink(relative_path)
        print(f"Symlink {relative_path} points to {target}")

        # Attempt to `git checkout` the target of the symlink
        return git_checkout(target)
    else:
        return git_checkout(relative_path)


def handle_ansible_file_not_found(stderr: str) -> bool:
    """Handle the case where Ansible reports a file not found on the controller."""
    patterns = [
        r"ERROR! vars file (.*) was not found",  # can have templates
        r"ERROR!.*\s([\S]+) could not be found",
        r"ERROR!.*\s([\S]+) was not found",
        r"Could not find or access '(.+)'",
        r"ERROR! the role '(.+)' was not found in",
    ]
    for pattern in patterns:
        match = re.search(pattern, stderr)
        if not match:
            continue
        missing_file = match.group(1)
        if "{{" in missing_file:
            print(f"template found: {missing_file}")
            missing_file = missing_file.split("{{")[0]
        print(f"Missing file reported by Ansible: {missing_file}")

        # Attempt to `git checkout` the missing file
        if restore_missing_file(missing_file):
            return True
    return False


def handle_ansible_variable(stderr: str) -> bool:
    pattern = r"The task includes an option with an undefined variable. The error was: '(.*)' is undefined"
    match = re.search(pattern, stderr)
    if not match:
        return False
    var = match.group(1)
    # Search for the undefined variable in each deleted file
    ref = ctx().git_ref
    deleted_files = get_deleted_files(ref=ref)
    for deleted_file in deleted_files:
        print(f"Searching for '{var}' in {deleted_file}...")
        try:
            show_result = subprocess.run(
                ["git", "show", f"{ref}:{deleted_file}"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            if var in show_result.stdout:
                print(f"Found '{var}' in {deleted_file}. Attempting to restore...")
                return restore_missing_file(deleted_file)
        except subprocess.CalledProcessError:
            print(f"Error while processing file {deleted_file}")
        except UnicodeDecodeError:
            print(f"Error reading file {deleted_file}")

    print(f"Variable '{var}' not found in any deleted files.")
    return False


def extract_mypy_names(error_message: str) -> T.Dict[str, T.Set[str]]:
    """
    Extracts quoted names and their associated filenames from mypy error messages.
    """
    pattern = r'(.+?):\d+: error: Name "(.*?)" is not defined  \[name-defined\]'
    files_missing_names: T.Dict[str, T.Set[str]] = {}
    for path, name in re.findall(pattern, error_message):
        if path not in files_missing_names:
            files_missing_names[path] = set()
        files_missing_names[path].add(name)
    return files_missing_names


def handle_mypy_errors(stdout: str) -> bool:
    """
    Attempt to fix every [name-defined] error that mypy reports.
    """
    files_with_errors = extract_mypy_names(stdout)
    if not files_with_errors:
        return False

    for filepath, names in files_with_errors.items():
        for name in names:
            success = do_repair(filepath, missing=name)
            if not success:
                # TODO
                raise RuntimeError(name)
    return True





def handle_generic_no_such_file(err: str) -> bool:
    """Handle generic 'No such file or directory' errors when we can't identify the specific file."""
    # Pattern: No such file or directory (os error 2)
    # This is a catch-all for runtime errors where the file isn't specified

    if "No such file or directory (os error 2)" not in err:
        return False

    # First, check for commonly missing configuration files
    # These are files that are often read at runtime
    common_config_files = [
        "test/fixtures/fixtures.json",
        "fixtures.json",
        "config.json",
        ".config.json",
    ]

    deleted_files = get_deleted_files(ref=ctx().git_ref)

    for config_file in common_config_files:
        if config_file in deleted_files:
            print(f"Found deleted config file that's likely needed: {config_file}")
            if restore_missing_file(config_file):
                return True

    # If there's no other context, we can't fix it
    # But let's look for any file paths mentioned nearby in the error
    lines = err.split('\n')

    # Look for potential file paths in the error
    for i, line in enumerate(lines):
        if "No such file or directory" in line:
            # Check surrounding lines for file paths
            context_start = max(0, i - 5)
            context_end = min(len(lines), i + 5)
            context = '\n'.join(lines[context_start:context_end])

            # Look for common file path patterns
            file_patterns = [
                r'`([^`]+\.[a-z]+)`',  # Files in backticks
                r'"([^"]+\.[a-z]+)"',  # Files in quotes
                r"'([^']+\.[a-z]+')",  # Files in single quotes
                r'\b([\w/-]+\.(?:txt|json|toml|rs|c|h|md))\b',  # Common extensions
            ]

            for pattern in file_patterns:
                matches = re.findall(pattern, context)
                for file_path in matches:
                    print(f"Found potential missing file: {file_path}")
                    if restore_missing_file(file_path):
                        return True

    print("Generic 'No such file' error but couldn't identify the file")
    return False


def handle_rust_env_not_defined(err: str) -> bool:
    """Handle Rust compile-time environment variable errors that might indicate missing build.rs."""
    # Pattern: error: environment variable `BUILD_TARGET` not defined at compile time
    #          --> crates/loader/src/loader.rs:578:28
    #          = help: use `std::env::var("BUILD_TARGET")` to read the variable at run time

    if "environment variable" not in err or "not defined at compile time" not in err:
        return False

    # Extract the variable name and file location
    var_match = re.search(r"environment variable `([^`]+)` not defined", err)
    file_match = re.search(r"--> ([^:]+):(\d+):(\d+)", err)

    if not var_match or not file_match:
        return False

    var_name = var_match.group(1)
    source_file = file_match.group(1)

    print(f"Environment variable {var_name} not defined in {source_file}")

    # Usually compile-time env vars are set by build.rs
    # Try to find and restore the build.rs file for this crate
    # Extract crate directory from source file path (e.g., crates/loader/src/loader.rs -> crates/loader)
    parts = source_file.split('/')
    if 'src' in parts:
        src_index = parts.index('src')
        crate_dir = '/'.join(parts[:src_index])
        build_rs_path = os.path.join(crate_dir, 'build.rs')

        print(f"Looking for build script: {build_rs_path}")
        if restore_missing_file(build_rs_path):
            print(f"Restored {build_rs_path}")
            return True

    return False


def handle_rust_module_not_found(err: str) -> bool:
    """Handle Rust compiler errors for missing module files."""
    # Pattern: error[E0583]: file not found for module `ffi`
    #          --> lib/binding_rust/lib.rs:5:1
    #          = help: to create the module `ffi`, create file "lib/binding_rust/ffi.rs"

    if "file not found for module" not in err:
        return False

    # Extract module name and suggested file path
    module_match = re.search(r"file not found for module `([^`]+)`", err)
    if not module_match:
        return False

    module_name = module_match.group(1)
    print(f"Missing Rust module: {module_name}")

    # Extract suggested file path from help message
    # Pattern: = help: to create the module `ffi`, create file "lib/binding_rust/ffi.rs" or "lib/binding_rust/ffi/mod.rs"
    file_match = re.search(r'create file "([^"]+\.rs)"', err)
    if file_match:
        suggested_file = file_match.group(1)
        print(f"Suggested file: {suggested_file}")

        # Try to restore the suggested file
        if restore_missing_file(suggested_file):
            return True

        # Also try the alternative path if mentioned (mod.rs)
        alt_match = re.search(r'create file "[^"]+" or "([^"]+\.rs)"', err)
        if alt_match:
            alt_file = alt_match.group(1)
            print(f"Trying alternative: {alt_file}")
            if restore_missing_file(alt_file):
                return True

    return False


def handle_rust_panic_no_such_file(err: str) -> bool:
    """Handle Rust build script panics caused by missing files."""
    # Pattern: thread 'main' panicked at path/to/file.rs:line:col:
    #          called `Result::unwrap()` on an `Err` value: Os { code: 2, kind: NotFound, message: "No such file or directory" }

    if "panicked at" not in err or "NotFound" not in err:
        return False

    # Extract the file that caused the panic
    panic_match = re.search(r"panicked at ([^:]+):(\d+):(\d+):", err)
    if not panic_match:
        return False

    panic_file = panic_match.group(1)
    panic_line = int(panic_match.group(2))

    print(f"Build script panic at {panic_file}:{panic_line}")

    # Try to find what file the build script was trying to access
    # Common patterns in build scripts:
    #   fs::copy("src/wasm/stdlib-symbols.txt", ...)
    #   File::open("path/to/file")
    #   include_str!("path/to/file")

    # Look for file paths in quotes near the panic
    file_patterns = [
        r'["\']([\w/.-]+\.\w+)["\']',  # Generic quoted file paths
        r'fs::copy\(["\']([^"\']+)["\']',  # fs::copy calls
        r'File::open\(["\']([^"\']+)["\']',  # File::open calls
        r'include_str!\(["\']([^"\']+)["\']',  # include_str! macro
    ]

    # Try to read the panic file to see what it's trying to access
    try:
        result = subprocess.run(
            ["git", "show", f"HEAD:{panic_file}"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if result.returncode == 0:
            lines = result.stdout.split('\n')
            # Get the line that caused the panic (and a few around it for context)
            if panic_line <= len(lines):
                context_lines = lines[max(0, panic_line - 3):min(len(lines), panic_line + 2)]
                context = '\n'.join(context_lines)

                # Search for file paths in the context
                for pattern in file_patterns:
                    matches = re.findall(pattern, context)
                    for file_path in matches:
                        print(f"Found potential missing file in build script: {file_path}")
                        if restore_missing_file(file_path):
                            return True
    except Exception as e:
        print(f"Error analyzing panic file: {e}")

    return False


def handle_cargo_couldnt_read(err: str) -> bool:
    """Handle cargo/rustc errors when it can't read a file."""
    # Pattern: error: couldn't read `crates/language/build.rs`: No such file or directory
    match = re.search(r"couldn't read `([^`]+)`:\s*No such file or directory", err)
    if not match:
        return False

    missing_file = match.group(1)
    print(f"Cargo couldn't read file: {missing_file}")
    return restore_missing_file(missing_file)


def handle_cargo_missing_library(err: str) -> bool:
    """Handle cargo errors when a library file is missing."""
    # Patterns:
    #   can't find library `name`, rename file to `src/lib.rs` or specify lib.path
    #   no targets specified in the manifest
    #   either src/lib.rs, src/main.rs, a [lib] section, or [[bin]] section must be present

    # Pattern 1: specific library/bench/bin missing
    # can't find library `name`, rename file to `src/lib.rs`
    # can't find `benchmark` bench at `benches/benchmark.rs` or `benches/benchmark/main.rs`
    match = re.search(r"can't find (?:`([^`]+)` )?(?:library|bench|bin) (?:`([^`]+)` )?at `([^`]+)`", err)
    if match:
        target_name = match.group(1) or match.group(2)
        suggested_path = match.group(3)
        print(f"Missing target: {target_name}, suggested path: {suggested_path}")

        # Try to extract the crate path from error
        # Pattern: failed to parse manifest at `/root/tree-sitter/crates/cli/Cargo.toml`
        crate_match = re.search(r"failed to parse manifest at [`']([^'`]+/Cargo\.toml)[`']", err)
        if crate_match:
            cargo_path = crate_match.group(1)
            # Convert to relative path
            if cargo_path.startswith('/root/tree-sitter/'):
                cargo_path = cargo_path.replace('/root/tree-sitter/', '')

            # Get the directory containing Cargo.toml
            crate_dir = os.path.dirname(cargo_path)
            print(f"Crate directory: {crate_dir}")

            # Prepend crate directory to suggested path
            full_path = os.path.join(crate_dir, suggested_path)
            print(f"Full path: {full_path}")

            # Try to restore the file
            if restore_missing_file(full_path):
                return True

        # Try without crate directory (for workspace root)
        if restore_missing_file(suggested_path):
            return True

        # Also try with underscores instead of hyphens (common Rust convention)
        alt_path = suggested_path.replace("-", "_")
        if alt_path != suggested_path:
            print(f"Trying alternative path: {alt_path}")
            if restore_missing_file(alt_path):
                return True

    # Pattern 1b: simpler library pattern
    match = re.search(r"can't find library `([^`]+)`, rename file to `([^`]+)`", err)
    if match:
        library_name = match.group(1)
        suggested_path = match.group(2)
        print(f"Missing library: {library_name}, suggested path: {suggested_path}")

        # Try to restore the suggested file
        if restore_missing_file(suggested_path):
            return True

        # Also try with underscores instead of hyphens (common Rust convention)
        alt_path = suggested_path.replace("-", "_")
        if alt_path != suggested_path:
            print(f"Trying alternative path: {alt_path}")
            if restore_missing_file(alt_path):
                return True

    # Pattern 2: no targets specified
    if "no targets specified in the manifest" in err or "either src/lib.rs, src/main.rs" in err:
        print("Cargo manifest has no targets, looking for src/lib.rs or src/main.rs")

        # Try to extract the crate path from error
        # Pattern: failed to parse manifest at `/root/tree-sitter/crates/xtask/Cargo.toml`
        crate_match = re.search(r"failed to parse manifest at [`']([^'`]+/Cargo\.toml)[`']", err)
        if crate_match:
            cargo_path = crate_match.group(1)
            # Convert to relative path
            if cargo_path.startswith('/root/tree-sitter/'):
                cargo_path = cargo_path.replace('/root/tree-sitter/', '')

            # Get the directory containing Cargo.toml
            crate_dir = os.path.dirname(cargo_path)
            print(f"Crate directory: {crate_dir}")

            # Try to restore src/lib.rs and src/main.rs
            restored_any = False
            for target_file in ['src/lib.rs', 'src/main.rs']:
                target_path = os.path.join(crate_dir, target_file)
                print(f"Trying to restore: {target_path}")
                if restore_missing_file(target_path):
                    restored_any = True

            if restored_any:
                return True

    return False


def handle_cargo_toml_not_found(err: str) -> bool:
    """Handle cargo errors when Cargo.toml is missing."""
    # Patterns:
    #   error: could not find `Cargo.toml` in `/path` or any parent directory
    #   error: failed to load manifest for workspace member
    #   failed to read `/path/to/Cargo.toml`
    is_cargo_error = (
        "could not find `Cargo.toml`" in err or
        "failed to load manifest" in err or
        ("failed to read" in err and "Cargo.toml" in err)
    )

    if not is_cargo_error:
        return False

    print("Cargo.toml not found, attempting to restore")

    # Try to extract specific path from error
    # Pattern: failed to read `/root/tree-sitter/crates/cli/Cargo.toml`
    path_match = re.search(r"failed to read [`']([^'`]+Cargo\.toml)[`']", err)
    if path_match:
        specific_path = path_match.group(1)
        # Convert to relative path
        if specific_path.startswith('/root/tree-sitter/'):
            relative_path = specific_path.replace('/root/tree-sitter/', '')
            print(f"Attempting to restore specific Cargo.toml: {relative_path}")
            if restore_missing_file(relative_path):
                return True

    # Try to restore Cargo.toml in current directory
    if restore_missing_file("Cargo.toml"):
        return True

    # Check deleted files for any Cargo.toml and restore all of them
    deleted_files = get_deleted_files(ref=ctx().git_ref)
    cargo_files = [f for f in deleted_files if f.endswith("Cargo.toml")]

    if cargo_files:
        print(f"Found {len(cargo_files)} deleted Cargo.toml files")
        # Restore all of them
        restored_any = False
        for cargo_file in cargo_files:
            print(f"Restoring {cargo_file}")
            if restore_missing_file(cargo_file):
                restored_any = True
        return restored_any

    return False




def handle_make_no_makefile_found(err: str) -> bool:
    """Handle make errors when no makefile is found in a subdirectory.
    
    Example errors:
        make[1]: *** No targets specified and no makefile found.  Stop.
        make: *** [Makefile:278: libterm/libtermlib.a] Error 2
        
        make[1]: Makefile: No such file or directory
    """
    if "no makefile found" not in err.lower() and "Makefile: No such file or directory" not in err:
        return False
    
    # Try to find which subdirectory is missing the Makefile
    # Look for the make[N]: Entering directory pattern
    dir_match = re.search(r"make\[\d+\]: Entering directory '([^']+)'", err)
    if not dir_match:
        return False
    
    subdir = dir_match.group(1)
    print(f"Make failed in subdirectory: {subdir}")
    
    # Get relative path
    cwd = os.getcwd()
    if subdir.startswith(cwd):
        subdir = subdir[len(cwd):].lstrip('/')
    
    # Look for Makefile in that subdirectory
    deleted_files = get_deleted_files(ref=ctx().git_ref)
    makefile_names = ['Makefile', 'makefile', 'GNUmakefile', 'Makefile.in']
    
    for makefile in makefile_names:
        makefile_path = os.path.join(subdir, makefile)
        if makefile_path in deleted_files:
            print(f"Found missing Makefile: {makefile_path}")
            return restore_missing_file(makefile_path)
    
    # Also try to restore all files in that subdirectory
    subdir_files = [f for f in deleted_files if f.startswith(subdir + '/')]
    if subdir_files:
        print(f"Restoring {len(subdir_files)} files from {subdir}/")
        restored_any = False
        for f in subdir_files:
            if restore_missing_file(f):
                restored_any = True
        return restored_any
    
    return False


def handle_make_missing_target(err: str) -> bool:
    """Handle make errors when a required source file is missing."""
    # Pattern: make: *** No rule to make target 'filename', needed by 'target'.  Stop.
    # or: make[N]: *** No rule to make target 'filename', needed by 'target'.  Stop.
    pattern = r"make(?:\[\d+\])?: \*\*\* No rule to make target '([^']+)', needed by"
    match = re.search(pattern, err)

    if not match:
        return False

    missing_file = match.group(1)
    print(f"Found missing make target: {missing_file}")
    
    # Check if this is from a subdirectory make
    # Look for "Entering directory" to get the subdir path
    dir_match = re.search(r"make\[\d+\]: Entering directory '([^']+)'", err)
    subdir = ""
    if dir_match:
        fulldir = dir_match.group(1)
        cwd = os.getcwd()
        if fulldir.startswith(cwd):
            subdir = fulldir[len(cwd):].lstrip('/')
            print(f"Subdirectory context: {subdir}")
    
    # If looking for an object file (.o), try to restore the source file instead
    if missing_file.endswith('.o'):
        # Try common source extensions
        base = missing_file[:-2]
        for ext in ['.c', '.cc', '.cpp', '.cxx', '.C']:
            source_file = base + ext
            # Try with subdirectory prefix first
            if subdir:
                full_path = os.path.join(subdir, source_file)
                print(f"Trying to restore source file: {full_path}")
                if restore_missing_file(full_path):
                    return True
            print(f"Trying to restore source file: {source_file}")
            if restore_missing_file(source_file):
                return True
    
    # Try with subdirectory prefix first
    if subdir:
        full_path = os.path.join(subdir, missing_file)
        print(f"Trying with subdirectory: {full_path}")
        if restore_missing_file(full_path):
            return True
    
    return restore_missing_file(missing_file)


def handle_make_recipe_failed(err: str) -> bool:
    """Handle make errors when a recipe fails to build a target.
    
    If the target file is tracked in git and deleted, restore it directly
    instead of trying to run the failing recipe.
    
    Example error:
        make: *** [Makefile:291: ex_vars.h] Error 1
    """
    # Pattern: make: *** [Makefile:line: target] Error N
    pattern = r"make: \*\*\* \[Makefile:\d+: ([^\]]+)\] Error \d+"
    match = re.search(pattern, err)
    
    if not match:
        return False
    
    target = match.group(1).strip()
    print(f"Make recipe failed for target: {target}")
    
    # Check if target is a deleted file we can restore
    ref = ctx().git_ref
    deleted_files = get_deleted_files(ref=ref)
    
    if target in deleted_files:
        print(f"Target {target} is a deleted file, restoring directly from git")
        return restore_missing_file(target)
    
    return False


def handle_cannot_open_file(err: str) -> bool:
    """Handle errors when a program cannot open a file."""
    # Pattern: "Error: Cannot open file 'example.c'"
    pattern = r"[Ee]rror:?\s+Cannot open file ['\"]([^'\"]+)['\"]"
    match = re.search(pattern, err)

    if not match:
        return False

    missing_file = match.group(1)
    print(f"Cannot open file: {missing_file}")
    return restore_missing_file(missing_file)




def handle_c_linker_missing_object(err: str) -> bool:
    """
    Handle C/C++ linker errors when object files are missing.

    Example error:
        /usr/bin/ld: cannot find exrecover.o: No such file or directory
        collect2: error: ld returned 1 exit status
    """
    # Pattern: /usr/bin/ld: cannot find X.o: No such file or directory
    pattern = r"/usr/bin/ld: cannot find ([^\s:]+\.o): No such file or directory"
    matches = re.findall(pattern, err)
    
    if not matches:
        return False
    
    print(f"Linker error: missing object files: {matches}")
    
    restored_any = False
    for obj_file in matches:
        # Try to restore the corresponding source file
        base = obj_file[:-2]
        for ext in ['.c', '.cc', '.cpp', '.cxx', '.C']:
            source_file = base + ext
            print(f"Trying to restore source file: {source_file}")
            if restore_missing_file(source_file):
                restored_any = True
                break
    
    return restored_any


def handle_ar_missing_object(err: str) -> bool:
    """
    Handle ar (archiver) errors when object files are missing.

    Example error:
        ar: onefile.o: No such file or directory
    """
    # Pattern: ar: X.o: No such file or directory
    pattern = r"ar: ([^\s:]+\.o): No such file or directory"
    matches = re.findall(pattern, err)
    
    if not matches:
        return False
    
    print(f"ar error: missing object files: {matches}")
    
    # Check if this is from a subdirectory make
    dir_match = re.search(r"make\[\d+\]: Entering directory '([^']+)'", err)
    subdir = ""
    if dir_match:
        fulldir = dir_match.group(1)
        cwd = os.getcwd()
        if fulldir.startswith(cwd):
            subdir = fulldir[len(cwd):].lstrip('/')
            print(f"Subdirectory context: {subdir}")
    
    restored_any = False
    for obj_file in matches:
        # Try to restore the corresponding source file
        base = obj_file[:-2]
        for ext in ['.c', '.cc', '.cpp', '.cxx', '.C']:
            source_file = base + ext
            # Try with subdirectory prefix first
            if subdir:
                full_path = os.path.join(subdir, source_file)
                print(f"Trying to restore source file: {full_path}")
                if restore_missing_file(full_path):
                    restored_any = True
                    break
            print(f"Trying to restore source file: {source_file}")
            if restore_missing_file(source_file):
                restored_any = True
                break
    
    return restored_any




def handle_c_compilation_error(err: str) -> bool:
    """
    Handle C/C++ compilation errors when header files or source files are missing.

    Example error:
        lib/src/language.c:2:10: fatal error: ./wasm_store.h: No such file or directory
            2 | #include "./wasm_store.h"
              |          ^~~~~~~~~~~~~~~~
        compilation terminated.
    """
    # Pattern: fatal error: <filename>: No such file or directory
    pattern = r"fatal error:\s+([^\s:]+):\s+No such file or directory"
    match = re.search(pattern, err)

    if not match:
        return False

    missing_file = match.group(1)
    print(f"C compilation error: missing file {missing_file}")

    # Remove ./ prefix if present
    if missing_file.startswith("./"):
        missing_file = missing_file[2:]

    # For header files, also try to restore the corresponding .c file
    restored_any = False
    if missing_file.endswith(".h"):
        # Try to restore both the header and the corresponding .c file
        c_file = missing_file[:-2] + ".c"
        print(f"Also attempting to restore corresponding C file: {c_file}")
        if restore_missing_file(c_file):
            print(f"Successfully restored {c_file}")
            restored_any = True

    # Try to restore the missing file
    if restore_missing_file(missing_file):
        print(f"Successfully restored {missing_file}")
        restored_any = True

    return restored_any


def handle_missing_test_output(err: str) -> bool:
    """
    Handle the case where test output is missing from expected output.
    This detects unified diff output showing missing test lines and restores
    the corresponding test functions.

    Example error:
        ERROR: Output does not match expected results!
        Expected 50 lines, got 49 lines
        Differences:
        --------------------------------------------------------------------------------
        --- python_feature_test.txt
        +++ actual output
        @@ -1,5 +1,4 @@
         01. Integer arithmetic: 10 + 5 = 15
        -02. Float operations: 3.14 * 2 = 6.28
         03. String concatenation: 'Hello' + ' World' = 'Hello World'
    """
    # Don't try to restore test output if there are errors preventing tests from running
    # Let other handlers deal with the root cause first
    if "IndentationError" in err or "SyntaxError" in err or "NameError" in err or "ImportError" in err or "AttributeError" in err:
        return False

    # Check if this looks like a unified diff showing missing test output
    if "Expected" not in err or "got" not in err or "lines" not in err:
        return False

    if "Differences:" not in err:
        return False

    # Look for lines starting with "-" that contain test output (pattern: "NN. Description")
    # These are lines that are in the expected output but missing from actual output
    missing_pattern = re.compile(r'^-(\d+)\.\s+(.+)', re.MULTILINE)
    matches = missing_pattern.findall(err)

    if not matches:
        return False

    print(f"Detected {len(matches)} missing test output lines")

    # Try to find the test file being run
    # Look in the command for a .py file that might be the test file
    test_file = None
    for arg in ctx().command:
        if arg.endswith(".py") and "test" in arg.lower():
            # This is likely the test runner, look for the file it's testing
            # In our case, test_python.py runs python_feature_test.py
            # We need to find python_feature_test.py
            pass
        if arg.endswith("_test.py"):
            # Try to infer the actual test file
            test_file = arg.replace("test_", "").replace(".py", "_test.py")
            break

    # For the specific case of test_python.py, we know it tests python_feature_test.py
    # Let's look for files matching the pattern
    if test_file is None:
        # Try to find python_feature_test.py or similar
        possible_files = ["python_feature_test.py"]
        for f in possible_files:
            if os.path.exists(f) or f in get_deleted_files(ref=ctx().git_ref):
                test_file = f
                break

    if test_file is None:
        print("Could not determine test file to repair")
        return False

    print(f"Repairing test file: {test_file}")

    # For each missing test number, try to restore the corresponding test function
    success = False
    for test_num, description in matches:
        # Test functions are typically named like test_02_floats
        # We need to find the function that matches test_{test_num}_*
        # Use a regex pattern that will match any function starting with test_{test_num}_
        # The pattern will be matched against labels like "function:test_02_floats"
        pattern = f"function:test_{test_num}_.*"
        print(f"Attempting to restore test {test_num}: {description}")
        print(f"Using pattern: {pattern}")

        try:
            if do_repair(test_file, missing=pattern):
                success = True
            else:
                print(f"Failed to restore test {test_num}")
        except Exception as e:
            print(f"Error restoring test {test_num}: {e}")
            # Continue trying other tests
            pass

    return success


# Order matters.
# Each handler is tested in order and the first to return True is used.
HANDLERS = [
    handle_cargo_toml_not_found,
    handle_cargo_missing_library,
    handle_cargo_couldnt_read,
    handle_rust_env_not_defined,
    handle_rust_module_not_found,
    handle_rust_panic_no_such_file,
    handle_make_no_makefile_found,
    handle_make_missing_target,
    handle_make_recipe_failed,
    handle_c_compilation_error,
    handle_c_linker_missing_object,
    handle_ar_missing_object,
    handle_cannot_open_file,
    handle_permission_denied,
    handle_executable_not_found,
    handle_missing_test_output,
    handle_mypy_errors,
    handle_orphaned_method,
    handle_indentation_error,
    handle_future_annotations,
    handle_module_attribute_error,
    handle_object_attribute_error,
    handle_circular_import_error,
    handle_import_error2,
    handle_missing_pyc,
    handle_missing_py_module,
    handle_missing_py_package,
    handle_import_error1,
    handle_import_name_error,
    handle_ansible_file_not_found,
    handle_ansible_variable,
    handle_file_not_found,
    handle_shell_command_not_found,
    handle_cat_no_such_file,
    handle_diff_no_such_file,
    handle_sh_cannot_open,
    handle_sh_cant_cd,
    handle_no_such_file_or_directory,
    handle_generic_no_such_file,
    handle_missing_file,
]

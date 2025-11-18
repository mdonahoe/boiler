import argparse
import dataclasses
import os
import subprocess
import re
import shutil
import sys
import typing as T

import py_repair

"""
git branch "boiling"
cp .git/index .git/boil.index
GIT_INDEX_FILE=.git/boil.index git add .boil hil/
GIT_INDEX_FILE=.git/boil.index git write-tree
git commit-tree 9cb6a377da0c7931ac1a112db026bbab67a6631e -p HEAD -m 'first boil: unhandled error'
git update-ref refs/heads/boiling becd92e6fb329986a153070791e36a294874605d

Also useful to reset the working directory to a particular tree state, without touching index
git restore --source boiling -- .
"""

BOILING_BRANCH = "boiling"


def save_changes(parent: str, message: str, branch_name: T.Optional[str] = None) -> str:
    """
    Commit the current working directory, relative to a parent.
    Also update a branch, if given.

    Returns the created commit hash.
    """
    index_file = ".git/boil.index"
    shutil.copyfile(".git/index", index_file)
    env = os.environ.copy()
    env["GIT_INDEX_FILE"] = index_file
    if os.path.isdir(".boil"):
        subprocess.check_call(["git", "add", ".boil"], env=env)
    subprocess.check_call(["git", "add", "-u"], env=env)
    tree = subprocess.check_output(["git", "write-tree"], env=env, text=True).strip()
    commit = subprocess.check_output(
        ["git", "commit-tree", tree, "-p", parent, "-m", message], env=env, text=True
    ).strip()
    if branch_name:
        subprocess.check_call(
            ["git", "update-ref", f"refs/heads/{branch_name}", commit]
        )
    return commit


@dataclasses.dataclass
class Session:
    """
    Common properties of the current boiling invocation
    """

    key: str
    git_ref: str
    iteration: int
    command: T.List[str]


CURRENT_SESSION = Session("", "HEAD", 0, [])


def ctx() -> Session:
    return CURRENT_SESSION


def run_command(command: T.List[str]) -> T.Tuple[str, str, int]:
    """
    Run a shell command and return its output, error and exit code.
    """
    print(f"Running: {' '.join(command)}")
    try:
        result = subprocess.run(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        return result.stdout, result.stderr, result.returncode
    except FileNotFoundError as e:
        return "", str(e), -1


def git_checkout(file_path: str, ref: str = "HEAD") -> bool:
    """Run git checkout for the given file path."""
    deleted_files = set(get_deleted_files(ref=ref))
    if file_path not in deleted_files:
        print(f"missing: {file_path}")
        return False

    if file_path.endswith(".py"):
        # special handling for python scripts
        print(f"repairing checkout {file_path}")
        return do_repair(file_path)

    command = ["git", "checkout", ref, "--", file_path]
    stdout, stderr, code = run_command(command)
    if code != 0:
        print("stdout:", stdout)
        print("stderr:", stderr)
        raise ValueError(file_path)
    success = os.path.exists(file_path)
    print(f"success = {success}")
    return success


def get_python_file_path(module_name: str) -> str:
    """Convert a Python module name to a file path."""
    return module_name.replace(".", "/") + ".py"


def get_python_init_path(module_name: str) -> str:
    """Convert a Python module name to a __init__.py path."""
    return module_name.replace(".", "/") + "/__init__.py"


def get_deleted_files(ref: str = "HEAD") -> T.Set[str]:
    """Get the list of deleted files from `git status`."""
    result = subprocess.run(
        ["git", "diff", "--name-status", ref], stdout=subprocess.PIPE, text=True
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
    # Convert the absolute path to a relative path (assuming your repo's root is in your current working directory)
    relative_path = os.path.relpath(missing_file)
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
    
    return False


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


def handle_name_error(stderr: str) -> bool:
    """
    Fix a NameError
    """
    # regex to find the filename and the name causing the NameError
    filepath, name = parse_traceback(stderr)
    if filepath is None:
        return False

    relative_path = os.path.relpath(filepath)
    print(f"repairing {relative_path} for {name=}")
    return do_repair(relative_path, missing=name)


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
        py_repair.repair(
            filename=file_path,
            commit=ref or ctx().git_ref,
            missing=missing,
            verbose=False,
        )
        return True
    except Exception:
        print(f"failed to repair {file_path} with {missing=}")
        sys.exit(1)
        return False


def handle_executable_not_found(stderr: str) -> bool:
    """Handle the case where the executable is missing."""
    if "No such file or directory" not in stderr:
        return False
    missing_executable = stderr.split(":")[-1].strip().strip("'")
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


HANDLERS = [
    handle_missing_test_output,
    handle_mypy_errors,
    handle_indentation_error,
    handle_future_annotations,
    handle_name_error,
    handle_module_attribute_error,
    handle_object_attribute_error,
    handle_circular_import_error,
    handle_import_error2,
    handle_missing_pyc,
    handle_executable_not_found,
    handle_missing_py_module,
    handle_missing_py_package,
    handle_import_error1,
    handle_import_name_error,
    handle_ansible_file_not_found,
    handle_ansible_variable,
    handle_file_not_found,
    handle_no_such_file_or_directory,
    handle_missing_file,
]


def fix(command: T.List[str], num_iterations: int) -> bool:
    """
    Repeatedly run a command, repairing files until it is fixed.
    """
    # create branches at the current location
    ref = ctx().git_ref
    ancestor_check = subprocess.call(
        ["git", "merge-base", "--is-ancestor", ref, BOILING_BRANCH]
    )
    if ancestor_check == 1:
        print("existing boiling session is stale. Deleting")
        subprocess.call(["git", "branch", "-D", BOILING_BRANCH])
        # Also delete the boil directory
        os.system("rm -rf .boil")
    elif ancestor_check == 128:
        # branch doesn't exist
        pass
    elif ancestor_check == 0:
        # branch exists and is a ancestor of HEAD. proceed.
        pass
    else:
        raise ValueError("f{ancestor_check=}")

    subprocess.call(["git", "branch", BOILING_BRANCH])

    start_commit = BOILING_BRANCH

    # add the current working directory to boil-start
    boil_commit = save_changes(
        parent=start_commit,
        message=f"boil_start\n\n{' '.join(command)}",
        branch_name=BOILING_BRANCH,
    )

    # load the iteration number from the .boil dir
    os.makedirs(".boil", exist_ok=True)
    n = len(os.listdir(".boil"))

    while True:
        n += 1
        print(f"Attempt {n}")
        # Run the main command
        stdout, stderr, code = run_command(command)
        if code == 0:
            # it worked!
            return True

        if code == -1:
            # special case for FileNotFound
            print("file not found")
            if handle_executable_not_found(stderr):
                continue
            else:
                raise ValueError("asdf")

        # Print the output for debugging purposes
        print(stdout)
        print(stderr)
        err = stdout + stderr
        with open(f".boil/iter{n}.{code}.out", "w") as out:
            out.write(err)

        exit = False
        for handler in HANDLERS:
            if handler(err) and has_changes():
                message = f"fixed with {handler}"
                break
        else:
            message = "failed to handle this type of error"
            exit = True

        if not has_changes(verbose=True):
            raise RuntimeError("no change")

        boil_commit = save_changes(
            parent=boil_commit,
            message=f"boil_{n}\n\n{message}",
            branch_name=BOILING_BRANCH,
        )

        if num_iterations is not None and n >= num_iterations:
            print(f"Reached iteration limit {n}")
            break
    return False


def has_changes(verbose:bool=False) -> bool:
    """
    Look for changes in the working directory relative to the boiling branch
    """
    index_file = ".git/boil.index"
    env = os.environ.copy()
    env["GIT_INDEX_FILE"] = index_file

    # Check for modified files
    result = subprocess.run(
        ["git", "diff", "--quiet", BOILING_BRANCH],
        capture_output=True,
        env=env
    )
    modified = result.returncode != 0

    # Check for untracked files
    untracked_result = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        capture_output=True,
        text=True,
        env=env,
    )
    untracked = False
    for line in untracked_result.stdout.splitlines():
        if ".boil" in line:
            continue
        print("new", line)
        untracked = True

    changed = modified or untracked

    # Print detailed diff if verbose
    if changed and verbose:
        print(" --- git diff start ---")
        subprocess.call(["git", "--no-pager", "diff", BOILING_BRANCH], env=env)
        print(" --- git diff end ---")

    return changed

def abort_boiling() -> int:
    """
    Abort the current boiling session and restore the working directory
    to the state before boiling started.
    """
    # Check if boiling branch exists
    check_branch = subprocess.run(
        ["git", "rev-parse", "--verify", BOILING_BRANCH],
        capture_output=True
    )
    if check_branch.returncode != 0:
        print("No active boiling session found.")
        return 1

    # Find the boil_start commit
    try:
        boil_start_commit = subprocess.check_output(
            ["git", "log", "--format=%H", "--grep", "boil_start", f"HEAD..{BOILING_BRANCH}],
            text=True
        ).strip().split('\n')[0]  # Get the first (most recent) match

        if not boil_start_commit:
            print("Error: Could not find boil_start commit on boiling branch.")
            return 1

        print(f"Found boil_start commit: {boil_start_commit}")

        # Get the parent of boil_start (the original state)
        original_commit = subprocess.check_output(
            ["git", "rev-parse", f"{boil_start_commit}^"],
            text=True
        ).strip()

        print(f"Restoring to original commit: {original_commit}")

        # Reset working directory to the original state
        subprocess.check_call(["git", "reset", "--hard", original_commit])

        # then apply the changes to the working directory
        subprocess.check_call(f"git show {boil_start_commit} | git apply", shell=True)

        print("Successfully aborted boiling session.")
        print("Working directory has been restored to pre-boiling state.")

        # Clean up .boil directory
        if os.path.isdir(".boil"):
            print("Removing .boil directory...")
            shutil.rmtree(".boil")

        return 0

    except subprocess.CalledProcessError as e:
        print(f"Error during abort: {e}")
        return 1


def main() -> int:
    global CURRENT_SESSION
    parser = argparse.ArgumentParser(description="Boil your code.")
    parser.add_argument("-n", type=int, help="number of interations")
    parser.add_argument("--ref", type=str, default="HEAD", help="a working commit")
    parser.add_argument(
        "--abort",
        action="store_true",
        help="abort current boiling session and restore working directory",
    )
    parser.add_argument(
        "--handle-error",
        type=str,
        default=None,
        help="path to pre-existing command output for error analysis",
    )

    # Use parse_known_args to separate known and unknown arguments
    args, unknown_args = parser.parse_known_args()

    # Handle abort command
    if args.abort:
        return abort_boiling()

    # Store the remaining arguments as a single command string
    # TODO(matt): parse leading --dash-commands and complain because they are probs typos.
    command = unknown_args

    # set the global session
    CURRENT_SESSION = Session("foo", args.ref, 0, command)

    # If the user passes the error output explicitly, we can handle it and exit.
    if args.handle_error:
        err = open(args.handle_error).read()
        for i, handler in enumerate(HANDLERS):
            print(handler)
            if handler(err):
                print(f"fixed with {handler}")
                break
        else:
            raise RuntimeError("failed to handle this type of error")
        return 0

    # Otherwise, we iteratively run the command and fix errors, up to n times.
    num_failing = 0
    success = fix(command, num_iterations=args.n)
    if not success:
        print(f"failed to fix: {command}")
        num_failing += 1
    else:
        print("success")
    return num_failing


if __name__ == "__main__":
    sys.exit(main())

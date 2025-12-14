import os
import subprocess
import typing as T

from helpers import run_command


def get_git_toplevel() -> str:
    """Get the git repository root directory."""
    return subprocess.check_output(
        ["git", "rev-parse", "--show-toplevel"], text=True
    ).strip()


def get_deleted_files(ref: str = "HEAD") -> T.List[str]:
    """Get the list of deleted files from `git status`.

    Returns a sorted list for deterministic behavior.
    """
    # Fallback: use the working directory state
    result = subprocess.run(
        ["git", "diff", "--name-status", ref], stdout=subprocess.PIPE, text=True
    )
    # TODO: what if result fails?
    deleted = [
        line.split()[-1] for line in result.stdout.splitlines() if line.startswith("D")
    ]
    return sorted(deleted)  # Sort for deterministic iteration


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


def get_git_dir() -> str:
    """Get the .git directory path, works from any subdirectory of a git repo."""
    return subprocess.check_output(
        ["git", "rev-parse", "--git-dir"], text=True
    ).strip()

def get_git_file_info(ref: str) -> T.Dict[str, T.Any]:
    """
    Get information about modified and deleted files in the current working directory.
    
    Returns:
        {
            "partial_files": [{"file": "dim.c", "line_ratio": "40/1001", "status": "M"}, ...],
            "deleted_files": ["file1.c", "file2.h"],
            "command": "make test"
        }
    """
    git_dir = get_git_dir()
    index_file = os.path.join(git_dir, "boil.index")
    env = os.environ.copy()
    env["GIT_INDEX_FILE"] = index_file
    
    partial_files = []
    deleted_files = []
    
    # Get list of modified and deleted files
    result = subprocess.run(
        ["git", "diff", "--name-status", ref],
        capture_output=True,
        text=True,
        env=env
    )
    
    for line in result.stdout.strip().split('\n'):
        if not line:
            continue
        parts = line.split(maxsplit=1)
        if len(parts) < 2:
            continue
        
        status, file_path = parts[0], parts[1]
        
        if status == 'D':
            deleted_files.append(file_path)
        elif status == 'M':
            # Count lines in modified file
            try:
                # Get current line count
                with open(file_path, 'r', errors='ignore') as f:
                    current_lines = len(f.read().splitlines())
                
                # Get total line count from git at the ref
                result = subprocess.run(
                    ["git", "show", f"{ref}:{file_path}"],
                    capture_output=True,
                    text=True,
                    # env=env
                )
                total_lines = len(result.stdout.splitlines())
                
                partial_files.append({
                    "file": file_path,
                    "line_ratio": f"{current_lines}/{total_lines}",
                })
            except Exception as e:
                print(f"Warning: Could not get line count for {file_path}: {e}")
                partial_files.append({
                    "file": file_path,
                    "line_ratio": "unknown",
                })
    
    return {
        "partial_files": partial_files,
        "deleted_files": deleted_files,
    }



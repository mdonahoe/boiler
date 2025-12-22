import subprocess
import typing as T


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


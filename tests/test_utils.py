#!/usr/bin/env python3
"""
Test utilities for boiler tests.

Provides common functions for setting up and running boil tests.
"""

import os
import subprocess
import shutil
import tempfile


class BoilTestContext:
    """Context manager for running boil tests with automatic cleanup"""

    def __init__(self, result):
        self.result = result
        self.tmpdir = result['tmpdir']
        self._cleanup_callback = result.get('_cleanup_callback')

    def __enter__(self):
        return self.result

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._cleanup_callback:
            self._cleanup_callback()
        return False


def copy_and_boil(
    src_dir,
    test_command=["make", "test"],
    boil_args=None,
    preserve_tmpdir=False,
    verify_before=True,
    delete_files=True,
    timeout=120,
    env_vars=None,
    special_file_handling=None
):
    """
    Copy a source directory to a temp folder, initialize git, commit files,
    optionally delete them, and run boil until it succeeds or fails.

    Args:
        src_dir: Path to the source directory to copy from
        test_command: Command to run to test (default: ["make", "test"])
        boil_args: Additional arguments to pass to boil (default: None)
        preserve_tmpdir: If True, don't delete tmpdir after test (default: False)
        verify_before: If True, verify test passes before deletion (default: True)
        delete_files: If True, delete files before boiling (default: True)
        timeout: Timeout for boil command in seconds (default: 120)
        env_vars: Dict of environment variables to set for boil (default: None)
        special_file_handling: Dict mapping file patterns to deletion behavior:
            - "clear": Clear file content instead of deleting
            - "skip": Don't delete the file
            Example: {"*.c": "clear", "important.txt": "skip"}

    Returns:
        BoilTestContext: Context manager that yields dict with keys:
            - tmpdir: Path to temporary directory
            - boil_result: CompletedProcess from boil command
            - success: Boolean indicating if boil succeeded
    """
    boiler_dir = os.path.dirname(os.path.dirname(__file__))
    boil_script = os.path.join(boiler_dir, "boil")

    if not os.path.exists(src_dir):
        raise ValueError(f"Source directory not found: {src_dir}")

    # Create temporary directory
    tmpdir = tempfile.mkdtemp(prefix="boil_test_")
    cleanup_callback = None if preserve_tmpdir else lambda: shutil.rmtree(tmpdir)

    try:
        # Initialize git repo
        subprocess.run(["git", "init"], cwd=tmpdir, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"],
                      cwd=tmpdir, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test User"],
                      cwd=tmpdir, check=True, capture_output=True)

        # Copy files from source directory
        for item in os.listdir(src_dir):
            # Skip hidden files/directories
            if item.startswith('.'):
                continue
            src = os.path.join(src_dir, item)
            dst = os.path.join(tmpdir, item)
            if os.path.isfile(src):
                shutil.copy2(src, dst)
            elif os.path.isdir(src):
                shutil.copytree(src, dst)

        # Make scripts executable if needed
        for item in os.listdir(src_dir):
            if not item.startswith('.'):
                item_path = os.path.join(tmpdir, item)
                if os.path.isfile(item_path) and os.access(os.path.join(src_dir, item), os.X_OK):
                    os.chmod(item_path, 0o755)

        # Commit all files
        subprocess.run(["git", "add", "."], cwd=tmpdir, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"],
                      cwd=tmpdir, check=True, capture_output=True)

        # Verify the test works before deletion
        if verify_before:
            result = subprocess.run(test_command, cwd=tmpdir, capture_output=True, text=True)
            if result.returncode != 0:
                raise AssertionError(
                    f"Test should pass before deletion. Output:\n{result.stdout}\n{result.stderr}"
                )

        # Delete files if requested
        if delete_files:
            for item in os.listdir(tmpdir):
                if item == ".git":
                    continue
                item_path = os.path.join(tmpdir, item)

                # Check for special handling
                should_clear = False
                should_skip = False
                if special_file_handling:
                    for pattern, behavior in special_file_handling.items():
                        # Simple pattern matching (supports exact match or *.ext)
                        if pattern.startswith('*'):
                            ext = pattern[1:]  # Remove the *
                            if item_path.endswith(ext):
                                if behavior == "clear":
                                    should_clear = True
                                elif behavior == "skip":
                                    should_skip = True
                        elif item == pattern or item_path.endswith(pattern):
                            if behavior == "clear":
                                should_clear = True
                            elif behavior == "skip":
                                should_skip = True

                if should_skip:
                    continue

                if os.path.isfile(item_path):
                    if should_clear:
                        # Clear the content
                        with open(item_path, "w"):
                            pass
                    else:
                        os.remove(item_path)
                elif os.path.isdir(item_path):
                    shutil.rmtree(item_path)

        # Prepare boil command
        boil_cmd = [boil_script] + (boil_args or []) + test_command

        # Prepare environment
        env = os.environ.copy()
        # Set MAKELEVEL to ensure consistent behavior with recursive make
        if 'MAKELEVEL' not in env:
            env['MAKELEVEL'] = '1'
        if env_vars:
            env.update(env_vars)

        # Run boil
        boil_result = subprocess.run(
            boil_cmd,
            cwd=tmpdir,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env
        )

        result = {
            'tmpdir': tmpdir,
            'boil_result': boil_result,
            'success': boil_result.returncode == 0,
            '_cleanup_callback': cleanup_callback
        }

        return BoilTestContext(result)

    except Exception as e:
        # If an error occurred, clean up now
        if cleanup_callback:
            cleanup_callback()
        raise

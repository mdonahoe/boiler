#!/usr/bin/env python3
"""
Test utilities for boiler tests.

Provides common functions for setting up and running boil tests.
"""

import os
import sys
import subprocess
import shutil
import tempfile
import glob
import json
import time


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

        Note: If preserve_tmpdir=False, the returned context manager will cleanup
        the tmpdir when exited. Use it with 'with' statement:
            with copy_and_boil(...) as result:
                tmpdir = result['tmpdir']
                # use tmpdir here
            # tmpdir is cleaned up here

    Raises:
        AssertionError: If verification steps fail
        subprocess.TimeoutExpired: If boil command times out
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
        # This causes make to print "Entering directory" messages which the
        # MakeEnteringDirectoryDetector can detect
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


def run_boil_with_profiling(
    src_dir,
    test_command=["make", "test"],
    boil_args=None,
    verbose=True,
    timeout=120
):
    """
    Run copy_and_boil with profiling and detailed output.

    This function is designed for profiling and debugging - it preserves
    the temporary directory and prints detailed timing information using
    boil --check.

    Args:
        src_dir: Path to the source directory to copy from
        test_command: Command to run to test (default: ["make", "test"])
        boil_args: Additional arguments to pass to boil (default: None)
        verbose: If True, set BOIL_VERBOSE=1 (default: True)
        timeout: Timeout for boil command in seconds (default: 120)

    Returns:
        tuple: (tmpdir, success) - Path to temp directory and whether boiling succeeded
    """
    env_vars = {}
    if verbose:
        env_vars['BOIL_VERBOSE'] = '1'

    print(f"\n{'='*60}")
    print("Running boil...")
    print(f"{'='*60}\n")

    start_time = time.time()

    # Use context manager but preserve_tmpdir=True means no cleanup
    with copy_and_boil(
        src_dir=src_dir,
        test_command=test_command,
        boil_args=boil_args,
        preserve_tmpdir=True,
        verify_before=True,
        delete_files=True,
        timeout=timeout,
        env_vars=env_vars
    ) as result:
        tmpdir = result['tmpdir']
        boil_result = result['boil_result']
        success = boil_result.returncode == 0

        total_time = time.time() - start_time

        print(f"\n{'='*60}")
        print(f"Total test time: {total_time:.3f}s")
        print(f"Exit code: {boil_result.returncode}")
        print(f"{'='*60}\n")

        # Run boil --check to analyze the session
        boiler_dir = os.path.dirname(os.path.dirname(__file__))
        boil_script = os.path.join(boiler_dir, "boil")
        check_result = subprocess.run(
            [boil_script, "--check"],
            cwd=tmpdir,
            capture_output=True,
            text=True
        )

        if check_result.returncode == 0:
            print(check_result.stdout)
        else:
            print(f"Warning: boil --check failed with exit code {check_result.returncode}")
            if check_result.stderr:
                print(f"Error: {check_result.stderr}")

        print(f"\nTemp directory preserved at: {tmpdir}")
        return tmpdir, success


def build_clue_to_detector_map(detector_registry):
    """Build mapping from clue_type to detector name"""
    mapping = {}

    # Use PATTERNS attribute from detectors to map clue_types
    for detector in detector_registry._detectors:
        detector_name = detector.name
        # Check if detector has PATTERNS attribute (Detector subclasses)
        if hasattr(detector, 'PATTERNS'):
            for clue_type in detector.PATTERNS.keys():
                # If multiple detectors produce the same clue_type, keep the first one
                # (in practice, each clue_type should map to one detector)
                if clue_type not in mapping:
                    mapping[clue_type] = detector_name

    return mapping


def build_clue_to_planner_map(planner_registry, clues):
    """Build mapping from clue_type to planner name"""
    mapping = {}
    for planner in planner_registry._planners:
        # Test which clue types this planner handles
        for clue_type in clues:
            if planner.can_handle(clue_type):
                mapping[clue_type] = planner.name
    return mapping


def build_action_to_executor_map(executor_registry):
    """Build mapping from action to executor name"""
    mapping = {}
    test_actions = ["restore_full", "restore_c_element", "restore_python_element"]
    for executor in executor_registry._executors:
        for action in test_actions:
            if executor.can_handle(action):
                mapping[action] = executor.name
    return mapping


def analyze_boil_debug(boil_dir):
    """
    Analyze .boil/ debug output to extract used detectors, planners, and executors.

    Args:
        boil_dir: Path to the .boil directory

    Returns:
        dict with keys: 'detectors', 'planners', 'executors'
    """
    from src.pipeline.detectors.registry import get_detector_registry
    from src.pipeline.planners.registry import get_planner_registry
    from src.pipeline.executors.registry import get_executor_registry

    used_detectors = set()
    used_planners = set()
    used_executors = set()

    # Get all pipeline JSON files
    json_files = glob.glob(os.path.join(boil_dir, "iter*.pipeline.json"))

    # Build mappings from clue_types/plan_types/actions to component names
    detector_registry = get_detector_registry()
    planner_registry = get_planner_registry()
    executor_registry = get_executor_registry()

    # Map clue_types to detectors
    clue_to_detector = build_clue_to_detector_map(detector_registry)
    # Map clue_types to planners
    clue_to_planner = build_clue_to_planner_map(planner_registry, clues=clue_to_detector.keys())
    # Map actions to executors
    action_to_executor = build_action_to_executor_map(executor_registry)

    # Process each JSON file
    for json_file in json_files:
        with open(json_file, 'r') as f:
            data = json.load(f)

        # Extract detectors from clues_detected
        for clue in data.get("clues_detected", []):
            clue_type = clue.get("clue_type", "")
            if clue_type in clue_to_detector:
                used_detectors.add(clue_to_detector[clue_type])

        # Extract planners from plans_generated/attempted
        for plan in data.get("plans_generated", []) + data.get("plans_attempted", []):
            clue_source = plan.get("clue_source", {})
            clue_type = clue_source.get("clue_type", "")
            if clue_type in clue_to_planner:
                used_planners.add(clue_to_planner[clue_type])

            # Also extract executors from actions
            action = plan.get("action", "")
            if action in action_to_executor:
                used_executors.add(action_to_executor[action])

    return {
        'detectors': sorted(used_detectors),
        'planners': sorted(used_planners),
        'executors': sorted(used_executors)
    }

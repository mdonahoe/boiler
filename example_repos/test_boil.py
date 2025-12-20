#!/usr/bin/env python3
"""
Profile example repo tests to find bottlenecks

Usage:
    python3 test_boil.py [repo_name] [options]

Arguments:
    repo_name       Name of the example repo to profile (default: dim)
                    Available: dim, simple, tree-sitter, todo

Options:
    -n, --max-iterations N    Maximum iterations for boil (default: 1000)
    -t, --timeout SECONDS     Timeout in seconds (default: 120)
    --no-verbose              Don't set BOIL_VERBOSE=1
    --loop-until-fail         Run multiple iterations to check for non-determinism
    --max-loops N             Number of iterations to run (default: 100)
    --generate-tests          Generate expected_components.json files for all example repos
    -h, --help                Show this help message
"""
import os
import sys
import argparse
import json
from datetime import datetime
import tempfile
import subprocess
import shutil
import glob

# Add parent directory to path (boiler root)
boiler_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, boiler_root)

from pipeline.handlers import register_all_handlers
from pipeline.detectors.registry import get_detector_registry
from pipeline.planners.registry import get_planner_registry
from pipeline.executors.registry import get_executor_registry
from tests.test_utils import run_boil_with_profiling


def get_available_repos():
    """Get list of available example repos"""
    example_repos_dir = os.path.dirname(os.path.abspath(__file__))

    if not os.path.exists(example_repos_dir):
        return []

    repos = []
    for item in os.listdir(example_repos_dir):
        repo_path = os.path.join(example_repos_dir, item)
        before_dir = os.path.join(repo_path, "before")
        if os.path.isdir(repo_path) and os.path.exists(before_dir):
            repos.append(item)

    return sorted(repos)


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

    Returns dict with keys: 'detectors', 'planners', 'executors'
    """
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


def profile_repo(repo_name, max_iterations=1000, timeout=120, verbose=True):
    """Profile a specific example repo

    Args:
        repo_name: Name of the example repo to profile
        max_iterations: Maximum iterations for boil
        timeout: Timeout in seconds
        verbose: Whether to enable verbose output

    Returns:
        tuple: (tmpdir, success) - Path to temp directory and whether boiling succeeded
    """
    register_all_handlers()

    example_repos_dir = os.path.dirname(os.path.abspath(__file__))
    example_before_dir = os.path.join(example_repos_dir, repo_name, "before")

    if not os.path.exists(example_before_dir):
        available = get_available_repos()
        print(f"Error: Example repo '{repo_name}' not found.")
        print(f"Available repos: {', '.join(available)}")
        sys.exit(1)

    print(f"Profiling example repo: {repo_name}")
    print(f"Working in temp directory...")

    boil_args = ["-n", str(max_iterations)]

    tmpdir, success = run_boil_with_profiling(
        src_dir=example_before_dir,
        test_command=["make", "test"],
        boil_args=boil_args,
        verbose=verbose,
        timeout=timeout
    )

    return tmpdir, success


def run_boil_and_analyze(repo_name, boiler_dir):
    """Run boil on a repo and return component usage"""
    print(f"\n{'='*80}")
    print(f"Analyzing {repo_name}...")
    print(f"{'='*80}")

    boil_script = os.path.join(boiler_dir, "boil")
    example_before_dir = os.path.join(boiler_dir, "example_repos", repo_name, "before")

    if not os.path.exists(example_before_dir):
        print(f"Warning: {example_before_dir} does not exist, skipping")
        return None

    # Create temporary directory
    with tempfile.TemporaryDirectory() as tmpdir:
        # Initialize git repo
        subprocess.run(["git", "init"], cwd=tmpdir, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"],
                      cwd=tmpdir, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test User"],
                      cwd=tmpdir, check=True, capture_output=True)

        # Copy files from before/ directory
        for item in os.listdir(example_before_dir):
            if item.startswith('.'):
                continue
            src = os.path.join(example_before_dir, item)
            dst = os.path.join(tmpdir, item)
            if os.path.isfile(src):
                shutil.copy2(src, dst)
            elif os.path.isdir(src):
                shutil.copytree(src, dst)

        # Make scripts executable
        for item in os.listdir(example_before_dir):
            if not item.startswith('.'):
                item_path = os.path.join(tmpdir, item)
                if os.path.isfile(item_path) and os.access(os.path.join(example_before_dir, item), os.X_OK):
                    os.chmod(item_path, 0o755)

        # Commit all files
        subprocess.run(["git", "add", "."], cwd=tmpdir, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"],
                      cwd=tmpdir, check=True, capture_output=True)

        # Delete all files (but keep .git)
        for item in os.listdir(tmpdir):
            if item == ".git":
                continue
            item_path = os.path.join(tmpdir, item)
            if os.path.isfile(item_path):
                if item_path.endswith("dim.c"):
                    # Clear content for dim.c
                    with open(item_path, "w"):
                        pass
                else:
                    os.remove(item_path)
            elif os.path.isdir(item_path):
                shutil.rmtree(item_path)

        # Run boil
        print(f"Running boil on {repo_name}...")
        boil_result = subprocess.run(
            [boil_script, "make", "test"],
            cwd=tmpdir,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )

        if boil_result.returncode != 0:
            print(f"Warning: boil failed for {repo_name}")
            print(f"stdout: {boil_result.stdout[-500:]}")
            print(f"stderr: {boil_result.stderr[-500:]}")
            # Still try to analyze if .boil exists

        # Analyze .boil/ debug output
        boil_dir = os.path.join(tmpdir, ".boil")
        if os.path.exists(boil_dir):
            components = analyze_boil_debug(boil_dir)
            return components
        else:
            print(f"Warning: No .boil directory found for {repo_name}")
            return None


def generate_tests():
    """Generate expected_components.json files for each example repo"""
    boiler_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    example_repos_dir = os.path.dirname(os.path.abspath(__file__))

    # Get all example repos
    repos = [d for d in os.listdir(example_repos_dir)
             if os.path.isdir(os.path.join(example_repos_dir, d))
             and d not in ['.git', '__pycache__']]

    print(f"Found example repos: {repos}")

    register_all_handlers()

    # Analyze each repo
    results = {}
    for repo_name in repos:
        components = run_boil_and_analyze(repo_name, boiler_dir)
        if components:
            results[repo_name] = components

    # Generate expected_components.json files
    print(f"\n{'='*80}")
    print("Generating expected_components.json files...")
    print(f"{'='*80}")

    for repo_name, components in results.items():
        expected_file = os.path.join(example_repos_dir, repo_name, "expected_components.json")

        output = {
            "detectors": components['detectors'],
            "planners": components['planners'],
            "executors": components['executors']
        }

        with open(expected_file, 'w') as f:
            json.dump(output, f, indent=2)

        print(f"\n{repo_name}:")
        print(f"  Detectors ({len(components['detectors'])}): {components['detectors']}")
        print(f"  Planners ({len(components['planners'])}): {components['planners']}")
        print(f"  Executors ({len(components['executors'])}): {components['executors']}")
        print(f"  Saved to: {expected_file}")

    print(f"\n{'='*80}")
    print("Done!")
    print(f"{'='*80}")


def loop_until_fail(repo_name, max_iterations=1000, timeout=120, verbose=True, max_loops=100):
    """Loop boiling multiple times, keeping a history of all runs

    Args:
        repo_name: Name of the example repo to profile
        max_iterations: Maximum iterations for boil
        timeout: Timeout in seconds
        verbose: Whether to enable verbose output
        max_loops: Total number of loop iterations to run

    Returns:
        dict: History of all runs
    """
    history = {
        'repo_name': repo_name,
        'max_iterations': max_iterations,
        'timeout': timeout,
        'start_time': datetime.now().isoformat(),
        'runs': []
    }

    print(f"\n{'='*60}")
    print(f"Running {max_loops} iterations")
    print(f"{'='*60}\n")

    for i in range(1, max_loops + 1):
        print(f"\n{'='*60}")
        print(f"Loop iteration {i}/{max_loops}")
        print(f"{'='*60}\n")

        tmpdir, success = profile_repo(
            repo_name=repo_name,
            max_iterations=max_iterations,
            timeout=timeout,
            verbose=verbose
        )

        run_info = {
            'iteration': i,
            'tmpdir': tmpdir,
            'success': success,
            'timestamp': datetime.now().isoformat()
        }
        history['runs'].append(run_info)

        status = "SUCCESS" if success else "FAILED"
        print(f"\n{'='*60}")
        print(f"Iteration {i}: {status}")
        print(f"Temp dir: {tmpdir}")
        print(f"{'='*60}\n")

    history['end_time'] = datetime.now().isoformat()
    history['total_runs'] = len(history['runs'])
    history['successful_runs'] = sum(1 for r in history['runs'] if r['success'])
    history['failed_runs'] = sum(1 for r in history['runs'] if not r['success'])

    # Save history to a JSON file
    history_file = f"boil_history_{repo_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(history_file, 'w') as f:
        json.dump(history, f, indent=2)

    print(f"\n{'='*60}")
    print(f"SUMMARY")
    print(f"{'='*60}")
    print(f"Total runs: {history['total_runs']}")
    print(f"Successful: {history['successful_runs']}")
    print(f"Failed: {history['failed_runs']}")
    print(f"\nHistory saved to: {history_file}")
    print(f"\nAll temp directories:")
    for run in history['runs']:
        status = "✓" if run['success'] else "✗"
        print(f"  {status} Run {run['iteration']}: {run['tmpdir']}")

    # Show comparison info if we have both successes and failures
    if history['successful_runs'] > 0 and history['failed_runs'] > 0:
        successful_runs = [r for r in history['runs'] if r['success']]
        failed_runs = [r for r in history['runs'] if not r['success']]
        print(f"\nFor comparison:")
        print(f"  First successful: {successful_runs[0]['tmpdir']}")
        print(f"  First failed: {failed_runs[0]['tmpdir']}")

    print(f"{'='*60}\n")

    return history


def main():
    parser = argparse.ArgumentParser(
        description="Profile example repo tests to find bottlenecks",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"Available repos: {', '.join(get_available_repos())}"
    )

    parser.add_argument(
        'repo_name',
        nargs='?',
        default='dim',
        help='Name of the example repo to profile (default: dim)'
    )

    parser.add_argument(
        '-n', '--max-iterations',
        type=int,
        default=1000,
        help='Maximum iterations for boil (default: 1000)'
    )

    parser.add_argument(
        '-t', '--timeout',
        type=int,
        default=120,
        help='Timeout in seconds (default: 120)'
    )

    parser.add_argument(
        '--no-verbose',
        action='store_true',
        help="Don't set BOIL_VERBOSE=1"
    )

    parser.add_argument(
        '--loop-until-fail',
        action='store_true',
        help='Run multiple iterations to check for non-determinism'
    )

    parser.add_argument(
        '--max-loops',
        type=int,
        default=100,
        help='Number of iterations to run (default: 100)'
    )

    parser.add_argument(
        '--generate-tests',
        action='store_true',
        help='Generate expected_components.json files for all example repos'
    )

    args = parser.parse_args()

    if args.generate_tests:
        generate_tests()
    elif args.loop_until_fail:
        loop_until_fail(
            repo_name=args.repo_name,
            max_iterations=args.max_iterations,
            timeout=args.timeout,
            verbose=not args.no_verbose,
            max_loops=args.max_loops
        )
    else:
        tmpdir, success = profile_repo(
            repo_name=args.repo_name,
            max_iterations=args.max_iterations,
            timeout=args.timeout,
            verbose=not args.no_verbose
        )

        status = "SUCCESS" if success else "FAILED"
        print(f"\nBoiling: {status}")
        print(f"To clean up: rm -rf {tmpdir}")


if __name__ == "__main__":
    main()

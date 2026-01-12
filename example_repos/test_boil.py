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
import shutil

# Add parent directory to path (boiler root)
boiler_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, boiler_root)

# from pipeline.handlers import register_all_handlers
from tests.test_utils import run_boil_with_profiling, analyze_boil_debug, copy_and_boil


def get_available_repos(include_slow=False):
    """Get list of available example repos

    Args:
        include_slow: If False, exclude repos with skip_slow.txt marker
    """
    example_repos_dir = os.path.dirname(os.path.abspath(__file__))

    if not os.path.exists(example_repos_dir):
        return []

    repos = []
    for item in os.listdir(example_repos_dir):
        repo_path = os.path.join(example_repos_dir, item)
        before_dir = os.path.join(repo_path, "before")
        skip_marker = os.path.join(repo_path, "skip_slow.txt")

        if os.path.isdir(repo_path) and os.path.exists(before_dir):
            if include_slow or not os.path.exists(skip_marker):
                repos.append(item)

    return sorted(repos)


def is_slow_repo(repo_name):
    """Check if a repo has the skip_slow.txt marker"""
    example_repos_dir = os.path.dirname(os.path.abspath(__file__))
    skip_marker = os.path.join(example_repos_dir, repo_name, "skip_slow.txt")
    return os.path.exists(skip_marker)


def profile_repo(repo_name, max_iterations=1000, timeout=120, verbose=True, force_slow=False):
    """Profile a specific example repo

    Args:
        repo_name: Name of the example repo to profile
        max_iterations: Maximum iterations for boil
        timeout: Timeout in seconds
        verbose: Whether to enable verbose output
        force_slow: If True, run even if repo has skip_slow.txt marker

    Returns:
        tuple: (tmpdir, success) - Path to temp directory and whether boiling succeeded
    """
    # register_all_handlers()

    example_repos_dir = os.path.dirname(os.path.abspath(__file__))
    example_before_dir = os.path.join(example_repos_dir, repo_name, "before")

    if not os.path.exists(example_before_dir):
        available = get_available_repos(include_slow=True)
        print(f"Error: Example repo '{repo_name}' not found.")
        print(f"Available repos: {', '.join(available)}")
        sys.exit(1)

    # Check for slow repo marker
    if is_slow_repo(repo_name) and not force_slow:
        skip_file = os.path.join(example_repos_dir, repo_name, "skip_slow.txt")
        print(f"Warning: '{repo_name}' is marked as slow (see {skip_file})")
        print(f"The default timeout ({timeout}s) may not be sufficient.")
        print(f"Use --include-slow to run anyway, or -t to set a longer timeout.")
        print(f"Example: python3 test_boil.py {repo_name} -t 3600 --include-slow")
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

    example_before_dir = os.path.join(boiler_dir, "example_repos", repo_name, "before")

    if not os.path.exists(example_before_dir):
        print(f"Warning: {example_before_dir} does not exist, skipping")
        return None

    print(f"Running boil on {repo_name}...")

    # Use copy_and_boil to ensure consistent behavior with test suite
    # Note: preserve_tmpdir=True so we can analyze .boil/ directory before cleanup
    try:
        with copy_and_boil(
            src_dir=example_before_dir,
            test_command=["make", "test"],
            preserve_tmpdir=True,  # We need to analyze before cleanup
            verify_before=True,
            delete_files=True,
            timeout=300,
            special_file_handling=None  # Match test suite behavior
        ) as result:
            tmpdir = result['tmpdir']
            boil_result = result['boil_result']
            success = result['success']

            if not success:
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
    finally:
        # Clean up tmpdir if it was created
        if 'tmpdir' in locals() and os.path.exists(tmpdir):
            shutil.rmtree(tmpdir)


def generate_tests():
    """Generate expected_components.json files for each example repo"""
    boiler_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    example_repos_dir = os.path.dirname(os.path.abspath(__file__))

    # Get all example repos
    repos = [d for d in os.listdir(example_repos_dir)
             if os.path.isdir(os.path.join(example_repos_dir, d))
             and d not in ['.git', '__pycache__']]

    print(f"Found example repos: {repos}")

    # register_all_handlers()

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
        epilog=f"Available repos: {', '.join(get_available_repos())}\nSlow repos (require --include-slow): {', '.join(r for r in get_available_repos(include_slow=True) if is_slow_repo(r)) or 'none'}"
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
        '--include-slow',
        action='store_true',
        help='Include repos marked as slow (have skip_slow.txt)'
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
            verbose=not args.no_verbose,
            force_slow=args.include_slow
        )

        status = "SUCCESS" if success else "FAILED"
        print(f"\nBoiling: {status}")
        print(f"To clean up: rm -rf {tmpdir}")


if __name__ == "__main__":
    main()

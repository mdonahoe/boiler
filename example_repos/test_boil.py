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
    -h, --help                Show this help message
"""
import os
import sys
import argparse
import json
from datetime import datetime

# Add parent directory to path (boiler root)
boiler_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, boiler_root)

from pipeline.handlers import register_all_handlers
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

    args = parser.parse_args()

    if args.loop_until_fail:
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

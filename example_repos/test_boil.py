#!/usr/bin/env python3
"""
Profile example repo tests to find bottlenecks

Usage:
    python3 test_boil.py [repo_name] [options]

Arguments:
    repo_name       Name of the example repo to profile (default: dim)
                    Available: dim, simple, tree-sitter, todo

Options:
    -n, --max-iterations N    Maximum iterations for boil (default: 20)
    -t, --timeout SECONDS     Timeout in seconds (default: 120)
    --no-verbose              Don't set BOIL_VERBOSE=1
    -h, --help                Show this help message
"""
import os
import sys
import argparse

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


def profile_repo(repo_name, max_iterations=20, timeout=120, verbose=True):
    """Profile a specific example repo

    Args:
        repo_name: Name of the example repo to profile
        max_iterations: Maximum iterations for boil
        timeout: Timeout in seconds
        verbose: Whether to enable verbose output

    Returns:
        str: Path to the temporary directory (preserved for inspection)
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

    tmpdir = run_boil_with_profiling(
        src_dir=example_before_dir,
        test_command=["make", "test"],
        boil_args=boil_args,
        verbose=verbose,
        timeout=timeout
    )

    return tmpdir


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
        default=20,
        help='Maximum iterations for boil (default: 20)'
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

    args = parser.parse_args()

    tmpdir = profile_repo(
        repo_name=args.repo_name,
        max_iterations=args.max_iterations,
        timeout=args.timeout,
        verbose=not args.no_verbose
    )

    print(f"\nTo clean up: rm -rf {tmpdir}")


if __name__ == "__main__":
    main()

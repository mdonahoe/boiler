#!/usr/bin/env python3
"""
Identify functions that can be removed from the codebase.
Uses function_stats.py to analyze function usage and suggests candidates for removal.
Can optionally use src_remove.py to remove the identified function.
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


def get_function_stats(files, only_declared=True):
    """
    Run function_stats.py on the given files and return the statistics.

    Args:
        files: List of file paths to analyze
        only_declared: If True, only include functions declared in the files

    Returns:
        Dict mapping function names to their statistics
    """
    # Convert to absolute paths to ensure they work from the boiler directory
    abs_files = [str(Path(f).resolve()) for f in files]

    cmd = ['python3', 'function_stats.py', '--format', 'json']
    if only_declared:
        cmd.append('--only-declared')
    cmd.extend(abs_files)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            cwd=Path(__file__).parent
        )
        stats = json.loads(result.stdout)
        return stats
    except subprocess.CalledProcessError as e:
        print(f"Error running function_stats.py: {e}", file=sys.stderr)
        print(f"stderr: {e.stderr}", file=sys.stderr)
        print(f"stdout: {e.stdout}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON from function_stats.py: {e}", file=sys.stderr)
        print(f"Result stdout: {result.stdout}", file=sys.stderr)
        sys.exit(1)


def rank_removable_functions(stats):
    """
    Rank functions by how easily they can be removed.

    Args:
        stats: Function statistics from get_function_stats

    Returns:
        List of tuples (function_name, score, reason, details)
        Sorted by score (higher = more removable)
    """
    ranked = []

    for func_name, func_stats in stats.items():
        num_declarations = len(func_stats['function_declaration'])
        num_calls = len(func_stats['function_call'])

        # Calculate removability score
        # Higher score = more removable
        if num_calls == 0:
            # Dead code - highest priority
            score = 1000
            reason = "Dead code (declared but never called)"
        elif num_calls <= 2:
            # Minimally used
            score = 500 - (num_calls * 100)
            reason = f"Minimally used ({num_calls} call{'s' if num_calls > 1 else ''})"
        elif num_calls <= 5:
            # Low usage
            score = 200 - (num_calls * 10)
            reason = f"Low usage ({num_calls} calls)"
        else:
            # Moderate/high usage
            score = 100 - min(num_calls, 90)
            reason = f"Moderate usage ({num_calls} calls)"

        details = {
            'declarations': num_declarations,
            'calls': num_calls,
            'declared_in': func_stats['function_declaration'],
            'called_in': func_stats['function_call']
        }

        ranked.append((func_name, score, reason, details))

    # Sort by score descending (most removable first)
    ranked.sort(key=lambda x: x[1], reverse=True)

    return ranked


def print_candidates(ranked, limit=None):
    """Print the ranked removable function candidates."""
    print("\n" + "="*70)
    print("REMOVABLE FUNCTION CANDIDATES")
    print("="*70 + "\n")

    if limit:
        ranked = ranked[:limit]

    for i, (func_name, score, reason, details) in enumerate(ranked, 1):
        print(f"{i}. {func_name}")
        print(f"   Score: {score}")
        print(f"   Reason: {reason}")
        print(f"   Declared in: {details['declarations']} file(s)")
        for f in set(details['declared_in']):
            print(f"     - {f}")
        if details['calls'] > 0:
            print(f"   Called in: {details['calls']} location(s)")
            for f in details['called_in']:
                print(f"     - {f}")
        print()


def verify_function_removed(func_name, src_file):
    """
    Verify that a function has been completely removed from a source file.
    Checks for:
    1. Function declarations
    2. Function calls
    3. Any identifier references (e.g., when used as a callback parameter)

    Args:
        func_name: Name of the function to verify
        src_file: Path to the source file

    Returns:
        Tuple of (declarations_found, references_found) - both should be empty lists
    """
    abs_file_path = str(Path(src_file).resolve())

    # First check using ast_analyzer for declarations and calls
    try:
        result = subprocess.run(
            ['python3', 'ast_analyzer.py', '--src-file', abs_file_path],
            capture_output=True,
            text=True,
            check=True,
            cwd=Path(__file__).parent
        )
        output = result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Error verifying removal in {src_file}: {e}", file=sys.stderr)
        print(f"stderr: {e.stderr}", file=sys.stderr)
        return None, None

    declarations = []
    calls = []

    for line in output.split('\n'):
        line = line.strip()
        if not line:
            continue

        if line.startswith('function_call: '):
            found_func = line.replace('function_call: ', '')
            if found_func == func_name:
                calls.append(line)
        elif line.startswith('function_declaration: '):
            found_func = line.replace('function_declaration: ', '')
            if found_func == func_name:
                declarations.append(line)

    # Also do a simple text search to catch any remaining references
    # (e.g., function name used as a callback parameter)
    try:
        with open(abs_file_path, 'r') as f:
            content = f.read()
            # Match the function name as a complete word (not part of another identifier)
            pattern = r'\b' + re.escape(func_name) + r'\b'
            matches = re.findall(pattern, content)
            if matches:
                # Count how many times it appears
                # If we found it, it means there are still references
                calls.extend([f"text reference"] * len(matches))
    except Exception as e:
        print(f"Warning: Could not perform text search: {e}", file=sys.stderr)

    return declarations, calls


def remove_function(func_name, src_file, inplace=False):
    """
    Remove a function from a source file using src_remove.py.

    Args:
        func_name: Name of the function to remove
        src_file: Path to the source file
        inplace: If True, modify the file in-place

    Returns:
        The modified source code (if not inplace) or None
    """
    cmd = ['python3', 'src_remove.py', '--src-file', src_file]
    if inplace:
        cmd.append('--inplace')
    cmd.append(func_name)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            cwd=Path(__file__).parent
        )

        # Verify the function was removed
        if inplace:
            declarations, references = verify_function_removed(func_name, src_file)
            if declarations is not None and references is not None:
                errors = []
                if declarations:
                    errors.append(f"Function '{func_name}' declaration still exists")
                if references:
                    errors.append(f"Function '{func_name}' is still referenced {len(references)} time(s)")

                if errors:
                    print(f"\n❌ ERROR: Removal verification failed for '{func_name}' in {src_file}:", file=sys.stderr)
                    for error in errors:
                        print(f"  - {error}", file=sys.stderr)
                    print(f"\nThe function could not be safely removed because it's still referenced.", file=sys.stderr)
                    print(f"You may need to manually remove call sites or references first.", file=sys.stderr)
                    sys.exit(1)

        if not inplace:
            return result.stdout
        return None
    except subprocess.CalledProcessError as e:
        print(f"Error running src_remove.py: {e}", file=sys.stderr)
        print(f"stderr: {e.stderr}", file=sys.stderr)
        sys.exit(1)


def test_removal_empirically(func_name, src_file, test_command='make test'):
    """
    Test if removing a function breaks the build/tests.

    Args:
        func_name: Name of the function to test
        src_file: Path to the source file
        test_command: Command to run to test (default: 'make test')

    Returns:
        Dict with keys:
            - 'removed': bool, whether removal succeeded
            - 'tests_passed': bool, whether tests passed after removal
            - 'error': str or None, error message if any
    """
    import shutil
    import tempfile

    result = {
        'removed': False,
        'tests_passed': False,
        'error': None,
        'test_output': ''
    }

    # Create backup
    backup_file = src_file + '.backup'
    try:
        shutil.copy2(src_file, backup_file)
    except Exception as e:
        result['error'] = f"Failed to create backup: {e}"
        return result

    try:
        # Try to remove the function
        try:
            remove_function(func_name, src_file, inplace=True)
            result['removed'] = True
        except SystemExit:
            # Removal failed (verification failed)
            result['error'] = "Removal verification failed"
            return result
        except Exception as e:
            result['error'] = f"Removal failed: {e}"
            return result

        # Run the test command
        try:
            test_result = subprocess.run(
                test_command.split(),
                capture_output=True,
                text=True,
                timeout=60,  # 60 second timeout
                cwd=Path(src_file).parent
            )
            result['test_output'] = test_result.stdout + test_result.stderr
            result['tests_passed'] = (test_result.returncode == 0)
        except subprocess.TimeoutExpired:
            result['error'] = "Test command timed out"
        except Exception as e:
            result['error'] = f"Test command failed: {e}"

    finally:
        # Always restore the backup
        try:
            shutil.move(backup_file, src_file)
        except Exception as e:
            print(f"WARNING: Failed to restore backup for {src_file}: {e}", file=sys.stderr)

    return result


def empirical_test_mode(files, ranked, num_tests, test_command):
    """
    Test removal of top N functions empirically by trying to remove them
    and running the test suite.

    Args:
        files: List of source files
        ranked: List of ranked removable functions
        num_tests: Number of functions to test
        test_command: Command to run tests
    """
    print(f"\n{'='*70}")
    print(f"EMPIRICAL REMOVAL TEST - Testing top {num_tests} candidates")
    print(f"Test command: {test_command}")
    print(f"{'='*70}\n")

    results = []

    for i, (func_name, score, reason, details) in enumerate(ranked[:num_tests], 1):
        print(f"[{i}/{num_tests}] Testing removal of '{func_name}'...")
        print(f"  Score: {score} - {reason}")

        # Get the first file where it's declared
        src_files = set(details['declared_in'])
        if not src_files:
            print(f"  ⚠️  Skipped: No declaration found\n")
            results.append({
                'function': func_name,
                'score': score,
                'reason': reason,
                'removed': False,
                'tests_passed': False,
                'error': 'No declaration found'
            })
            continue

        src_file = list(src_files)[0]
        print(f"  Declared in: {src_file}")

        # Test the removal
        test_result = test_removal_empirically(func_name, src_file, test_command)

        # Report results
        if not test_result['removed']:
            print(f"  ❌ Removal failed: {test_result['error']}")
        elif test_result['tests_passed']:
            print(f"  ✅ Tests PASSED - Safe to remove!")
        else:
            print(f"  ⚠️  Tests FAILED - Removal would break tests")
            if test_result['error']:
                print(f"     Error: {test_result['error']}")

        print()

        results.append({
            'function': func_name,
            'score': score,
            'reason': reason,
            'removed': test_result['removed'],
            'tests_passed': test_result['tests_passed'],
            'error': test_result.get('error'),
            'test_output': test_result.get('test_output', '')
        })

    # Print summary report
    print(f"\n{'='*70}")
    print("EMPIRICAL TEST REPORT")
    print(f"{'='*70}\n")

    safe_to_remove = [r for r in results if r['removed'] and r['tests_passed']]
    breaks_tests = [r for r in results if r['removed'] and not r['tests_passed']]
    failed_removal = [r for r in results if not r['removed']]

    print(f"Summary:")
    print(f"  Total tested: {len(results)}")
    print(f"  ✅ Safe to remove (tests pass): {len(safe_to_remove)}")
    print(f"  ⚠️  Breaks tests: {len(breaks_tests)}")
    print(f"  ❌ Failed removal: {len(failed_removal)}")
    print()

    if safe_to_remove:
        print(f"Functions that can be safely removed:")
        for r in safe_to_remove:
            print(f"  ✅ {r['function']} (score: {r['score']}) - {r['reason']}")
        print()

    if breaks_tests:
        print(f"Functions that break tests when removed:")
        for r in breaks_tests:
            print(f"  ⚠️  {r['function']} (score: {r['score']}) - {r['reason']}")
            if r['error']:
                print(f"     Error: {r['error']}")
        print()

    if failed_removal:
        print(f"Functions that couldn't be removed:")
        for r in failed_removal:
            print(f"  ❌ {r['function']} - {r['error']}")
        print()

    return results


def main():
    parser = argparse.ArgumentParser(
        description='Identify functions that can be removed from the codebase'
    )
    parser.add_argument('files', nargs='+', help='Source files to analyze')
    parser.add_argument('--limit', type=int, help='Limit number of candidates to show')
    parser.add_argument('--include-external', action='store_true',
                       help='Include external/library functions in analysis')
    parser.add_argument('--remove', metavar='FUNCTION_NAME',
                       help='Remove the specified function from its source file(s)')
    parser.add_argument('--inplace', action='store_true',
                       help='Modify files in-place when using --remove (requires --remove)')
    parser.add_argument('--auto-remove-top', action='store_true',
                       help='Automatically remove the top candidate (highest score)')
    parser.add_argument('--test-removal', action='store_true',
                       help='Empirically test removal of top candidates by running tests')
    parser.add_argument('--num-tests', type=int, default=10,
                       help='Number of functions to test empirically (default: 10)')
    parser.add_argument('--test-command', default='make test',
                       help='Command to run for testing (default: "make test")')
    args = parser.parse_args()

    if args.inplace and not (args.remove or args.auto_remove_top):
        print("Error: --inplace requires --remove or --auto-remove-top", file=sys.stderr)
        sys.exit(1)

    # Get function statistics
    print(f"Analyzing {len(args.files)} file(s)...", file=sys.stderr)
    stats = get_function_stats(args.files, only_declared=not args.include_external)

    if not stats:
        print("No functions found to analyze.", file=sys.stderr)
        sys.exit(0)

    # Rank functions by removability
    ranked = rank_removable_functions(stats)

    # Empirical testing mode
    if args.test_removal:
        empirical_test_mode(args.files, ranked, args.num_tests, args.test_command)
        sys.exit(0)

    # Auto-remove top candidate if requested
    if args.auto_remove_top:
        if not ranked:
            print("No candidates to remove.", file=sys.stderr)
            sys.exit(0)

        top_func, score, reason, details = ranked[0]
        print(f"\nAuto-removing top candidate: {top_func}", file=sys.stderr)
        print(f"  Score: {score}", file=sys.stderr)
        print(f"  Reason: {reason}", file=sys.stderr)

        # Remove from all files where it's declared
        for src_file in set(details['declared_in']):
            print(f"  Removing from: {src_file}", file=sys.stderr)
            remove_function(top_func, src_file, inplace=args.inplace)
            if args.inplace:
                print(f"  ✓ Modified {src_file}", file=sys.stderr)

        if not args.inplace:
            print("\nNote: Files not modified. Use --inplace to apply changes.", file=sys.stderr)

        sys.exit(0)

    # Manual remove if requested
    if args.remove:
        func_name = args.remove

        if func_name not in stats:
            print(f"Error: Function '{func_name}' not found in analyzed files.", file=sys.stderr)
            sys.exit(1)

        details = stats[func_name]

        # Remove from all files where it's declared
        for src_file in set(details['function_declaration']):
            print(f"Removing {func_name} from: {src_file}", file=sys.stderr)
            result = remove_function(func_name, src_file, inplace=args.inplace)

            if args.inplace:
                print(f"✓ Modified {src_file}", file=sys.stderr)
            else:
                print(f"\n--- {src_file} (modified) ---")
                print(result)

        if not args.inplace:
            print("\nNote: Files not modified. Use --inplace to apply changes.", file=sys.stderr)

        sys.exit(0)

    # Show candidates
    print_candidates(ranked, limit=args.limit)


if __name__ == '__main__':
    main()

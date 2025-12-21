#!/usr/bin/env python3
"""
Compute statistics for function identifiers across multiple source files.
Uses ast_analyzer.py to extract function calls and declarations from each file.
"""
import argparse
import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path


def analyze_file(file_path):
    """
    Run ast_analyzer.py on a file and parse its output.

    Args:
        file_path: Path to the source file to analyze

    Returns:
        Dict with 'calls' and 'declarations' lists containing function names
    """
    # Convert to absolute path to ensure it works from any working directory
    abs_file_path = str(Path(file_path).resolve())

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
        print(f"Error analyzing {file_path}: {e}", file=sys.stderr)
        print(f"stderr: {e.stderr}", file=sys.stderr)
        print(f"stdout: {e.stdout}", file=sys.stderr)
        return {'calls': [], 'declarations': []}
    except FileNotFoundError:
        print("Error: ast_analyzer.py not found or python3 not available", file=sys.stderr)
        sys.exit(1)

    calls = []
    declarations = []

    for line in output.split('\n'):
        line = line.strip()
        if not line:
            continue

        if line.startswith('function_call: '):
            func_name = line.replace('function_call: ', '')
            calls.append(func_name)
        elif line.startswith('function_declaration: '):
            func_name = line.replace('function_declaration: ', '')
            declarations.append(func_name)

    return {'calls': calls, 'declarations': declarations}


def compute_stats(files):
    """
    Compute statistics for function identifiers across multiple files.

    Args:
        files: List of file paths to analyze

    Returns:
        Dict mapping function names to their stats
    """
    # Use defaultdict to automatically create nested dicts
    stats = defaultdict(lambda: {'function_call': [], 'function_declaration': []})

    for file_path in files:
        print(f"Analyzing {file_path}...", file=sys.stderr)
        results = analyze_file(file_path)

        # Add each declaration (one per file typically)
        for func_name in results['declarations']:
            stats[func_name]['function_declaration'].append(file_path)

        # Add each call (can be multiple per file)
        for func_name in results['calls']:
            stats[func_name]['function_call'].append(file_path)

    # Convert defaultdict to regular dict for cleaner output
    return dict(stats)


def main():
    parser = argparse.ArgumentParser(
        description='Compute function identifier statistics across multiple source files'
    )
    parser.add_argument('files', nargs='+', help='Source files to analyze')
    parser.add_argument('--format', choices=['json', 'pretty'], default='pretty',
                       help='Output format (default: pretty)')
    parser.add_argument('--only-declared', action='store_true',
                       help='Only include functions that are declared in the analyzed files (skip external functions)')
    args = parser.parse_args()

    stats = compute_stats(args.files)

    # Filter out functions that aren't declared if --only-declared is set
    if args.only_declared:
        stats = {
            func_name: func_stats
            for func_name, func_stats in stats.items()
            if func_stats['function_declaration']
        }

    if args.format == 'json':
        # Output as JSON
        print(json.dumps(stats, indent=2))
    else:
        # Pretty print format
        print("\n" + "="*60)
        print("FUNCTION IDENTIFIER STATISTICS")
        print("="*60 + "\n")

        for func_name in sorted(stats.keys()):
            print(f"Function: {func_name}")
            print("-" * 40)

            if stats[func_name]['function_declaration']:
                print(f"  Declarations ({len(stats[func_name]['function_declaration'])}):")
                for file_path in stats[func_name]['function_declaration']:
                    print(f"    - {file_path}")

            if stats[func_name]['function_call']:
                print(f"  Calls ({len(stats[func_name]['function_call'])}):")
                for file_path in stats[func_name]['function_call']:
                    print(f"    - {file_path}")

            print()


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
Analyze boil history and show restoration sequence with divergences

This script reads a boil history JSON file and produces a readable text file
showing the restoration sequence, with attempts grouped by what they restored.

Usage:
    python3 analyze_boil_history.py boil_history_tree-sitter_20251207_164740.json
"""

import argparse
import json
import os
import sys
from collections import defaultdict


def get_plans_for_iteration(tmpdir, iteration_num):
    """
    Get the list of plans attempted in a specific iteration

    Args:
        tmpdir: Path to the temporary boil directory
        iteration_num: The iteration number (1-indexed)

    Returns:
        list: List of plan dictionaries, or None if iteration doesn't exist
    """
    pipeline_file = os.path.join(tmpdir, '.boil', f'iter{iteration_num}.pipeline.json')

    if not os.path.exists(pipeline_file):
        return None

    try:
        with open(pipeline_file, 'r') as f:
            pipeline_data = json.load(f)

        # Get the plans_attempted list
        plans = pipeline_data.get('plans_attempted', [])
        return plans
    except (json.JSONDecodeError, KeyError, IOError) as e:
        print(f"Warning: Could not parse {pipeline_file}: {e}", file=sys.stderr)
        return None


def format_plan(plan):
    """
    Format a plan into a readable string

    Args:
        plan: Plan dictionary from pipeline JSON

    Returns:
        str: Formatted plan string like "[clue_type -> plan_type -> action] target_file"
    """
    clue_type = plan.get('clue_source', {}).get('clue_type', 'unknown')
    plan_type = plan.get('plan_type', 'unknown')
    action = plan.get('action', 'unknown')
    target_file = plan.get('target_file', 'unknown')

    return f"[{clue_type} -> {plan_type} -> {action}] {target_file}"


def get_tmpdir_basename(tmpdir):
    """Get just the last component of the tmpdir path"""
    return os.path.basename(tmpdir)


def analyze_history(history_file, output_file):
    """
    Analyze a boil history file and produce a readable restoration sequence

    Args:
        history_file: Path to the boil history JSON file
        output_file: Path to write the output text file
    """
    with open(history_file, 'r') as f:
        history = json.load(f)

    # Find the maximum iteration number across all runs
    max_iteration = 0
    for run in history['runs']:
        tmpdir = run['tmpdir']
        if not os.path.exists(tmpdir):
            continue

        boil_dir = os.path.join(tmpdir, '.boil')
        if not os.path.exists(boil_dir):
            continue

        # Count pipeline files to find max iteration
        for filename in os.listdir(boil_dir):
            if filename.startswith('iter') and filename.endswith('.pipeline.json'):
                iter_num = int(filename.replace('iter', '').replace('.pipeline.json', ''))
                max_iteration = max(max_iteration, iter_num)

    print(f"Found maximum iteration: {max_iteration}", file=sys.stderr)
    print(f"Analyzing {len(history['runs'])} runs...", file=sys.stderr)

    # Build the output
    with open(output_file, 'w') as out:
        # Write header
        out.write(f"Restoration Sequence Analysis\n")
        out.write(f"Source: {history_file}\n")
        out.write(f"Repo: {history.get('repo_name')}\n")
        out.write(f"Total runs: {history.get('total_runs')}\n")
        out.write(f"Max iteration: {max_iteration}\n")
        out.write(f"\n{'='*80}\n\n")

        # Process each iteration
        for iteration_num in range(1, max_iteration + 1):
            # Collect plans for each run
            run_plans = {}  # tmpdir -> list of plans

            for run in history['runs']:
                tmpdir = run['tmpdir']
                if not os.path.exists(tmpdir):
                    continue

                plans = get_plans_for_iteration(tmpdir, iteration_num)
                if plans is not None:
                    run_plans[tmpdir] = plans

            if not run_plans:
                continue

            # Find max number of plans in this iteration
            max_plans = max(len(plans) for plans in run_plans.values())

            # Process each plan index
            for plan_idx in range(max_plans):
                # Group runs by what plan they executed
                plan_groups = defaultdict(list)  # formatted_plan -> list of tmpdirs

                for tmpdir, plans in run_plans.items():
                    if plan_idx < len(plans):
                        plan = plans[plan_idx]
                        formatted = format_plan(plan)
                        plan_groups[formatted].append(tmpdir)
                    # If this run didn't have this many plans, skip it

                if not plan_groups:
                    continue

                # Write this iteration.plan
                out.write(f"Iteration {iteration_num}.{plan_idx}:\n")

                # Sort groups by size (largest first) for readability
                sorted_groups = sorted(plan_groups.items(), key=lambda x: len(x[1]), reverse=True)

                for formatted_plan, tmpdirs in sorted_groups:
                    # Get basename of first tmpdir
                    first = get_tmpdir_basename(tmpdirs[0])
                    count = len(tmpdirs) - 1

                    if count == 0:
                        out.write(f"    * ({first}): {formatted_plan}\n")
                    else:
                        out.write(f"    * ({first} and {count} others): {formatted_plan}\n")

                out.write("\n")

    print(f"\nOutput written to: {output_file}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(
        description="Analyze boil history and show restoration sequence",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        'history_file',
        help='Path to the boil history JSON file'
    )

    parser.add_argument(
        '-o', '--output',
        help='Output text file (default: <history_file>_sequence.txt)'
    )

    args = parser.parse_args()

    if not os.path.exists(args.history_file):
        print(f"Error: History file not found: {args.history_file}", file=sys.stderr)
        return 1

    # Determine output file
    if args.output:
        output_file = args.output
    else:
        base = os.path.splitext(args.history_file)[0]
        output_file = f"{base}_sequence.txt"

    analyze_history(args.history_file, output_file)

    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
Analyze an active boil session in the current working directory.

Usage:
    python3 analyze_boil_logs.py

This will scan all .boil/iter*.pipeline.json files and show:
1. Overall boil session status (succeeded, stuck, or in progress)
2. Which legacy handlers are used most often
3. Which errors the pipeline successfully handles
4. Migration priority recommendations
"""

import json
import os
import sys
import re
from collections import Counter, defaultdict
from datetime import datetime


def get_session_status():
    """Determine if the boil session succeeded, is stuck, or still in progress"""
    boil_dir = ".boil"
    
    # Check for completion marker
    completed_file = os.path.join(boil_dir, "completed")
    if os.path.exists(completed_file):
        try:
            with open(completed_file, "r") as f:
                result = f.read().strip()
                return f"✓ SUCCEEDED", result
        except:
            return "✓ SUCCEEDED", "Unknown"
    
    # Get all iteration numbers to detect infinite loops
    json_files = sorted([
        f for f in os.listdir(boil_dir)
        if re.match(r"iter\d+\.pipeline\.json", f)
    ])
    
    if not json_files:
        return "? UNKNOWN", "No pipeline files found"
    
    # Extract iteration numbers
    iterations = []
    for f in json_files:
        match = re.match(r"iter(\d+)\.pipeline\.json", f)
        if match:
            iterations.append(int(match.group(1)))
    
    if not iterations:
        return "? UNKNOWN", "Could not parse iteration numbers"
    
    iterations.sort()
    max_iter = iterations[-1]
    
    # Check if any recent iteration succeeded (could indicate success, then retried and failed)
    # Check backwards from max_iter to handle cases where boil succeeded then continued
    for i in range(max_iter, max(0, max_iter - 10), -1):
        last_json = os.path.join(boil_dir, f"iter{i}.pipeline.json")
        if os.path.exists(last_json):
            try:
                with open(last_json, "r") as f:
                    data = json.load(f)
                    if data.get("success"):
                        if i == max_iter:
                            return "✓ SUCCEEDED", f"Completed successfully at iteration {i}"
                        else:
                            return "✓ SUCCEEDED", f"Completed successfully at iteration {i} (retried but failed at {max_iter})"
            except:
                pass
    
    # Check if stuck in a loop (many iterations with similar failures)
    if max_iter > 20:
        # Likely stuck - check if recent iterations are failing the same way
        recent_failures = []
        for i in range(max(1, max_iter - 5), max_iter + 1):
            path = os.path.join(boil_dir, f"iter{i}.pipeline.json")
            if os.path.exists(path):
                try:
                    with open(path, "r") as f:
                        data = json.load(f)
                        if not data.get("success"):
                            error_msg = data.get("error_message", "unknown")
                            recent_failures.append(error_msg)
                except:
                    pass
        
        if recent_failures and len(set(recent_failures)) <= 2:
            return "⚠ STUCK", f"Max {max_iter} iterations reached with repeating failures"
        else:
            return "⚠ STUCK", f"Max {max_iter} iterations (likely infinite loop)"
    
    # If we haven't found a success, check the last iteration for detailed status
    last_json = os.path.join(boil_dir, f"iter{max_iter}.pipeline.json")
    if os.path.exists(last_json):
        try:
            with open(last_json, "r") as f:
                data = json.load(f)
                error = data.get("error_message", "unknown")
                return "⏳ IN PROGRESS", f"Iteration {max_iter}: {error}"
        except:
            return "? UNKNOWN", f"Could not read iter{max_iter}.pipeline.json"
    
    return "⏳ IN PROGRESS", f"Iterations {min(iterations)}-{max_iter} completed"


def analyze_legacy_usage():
    """Analyze legacy handler usage from JSON debug files"""

    # Find all pipeline JSON files
    boil_dir = ".boil"
    if not os.path.exists(boil_dir):
        print(f"No {boil_dir} directory found. Run boil.py first.")
        return 1

    # Print session status first
    print("=" * 80)
    print("BOIL SESSION STATUS")
    print("=" * 80)
    status, details = get_session_status()
    print(f"{status}")
    print(f"Details: {details}")
    print()

    json_files = [
        f for f in os.listdir(boil_dir)
        if f.endswith(".pipeline.json")
    ]

    if not json_files:
        print(f"No pipeline JSON files found in {boil_dir}")
        return 1

    print(f"Found {len(json_files)} pipeline iterations\n")

    # Counters
    legacy_handler_usage = Counter()
    pipeline_successes = 0
    pipeline_failures = 0
    error_types_detected = Counter()
    error_types_not_detected = defaultdict(list)
    failure_reasons = Counter()

    # Analyze each file
    for json_file in sorted(json_files):
        path = os.path.join(boil_dir, json_file)

        try:
            with open(path, "r") as f:
                data = json.load(f)
        except Exception as e:
            print(f"Warning: Could not read {json_file}: {e}")
            continue

        # Count pipeline success/failure
        if data.get("success"):
            pipeline_successes += 1
        else:
            pipeline_failures += 1
            # Track failure reasons
            error_msg = data.get("error_message", "unknown error")
            failure_reasons[error_msg] += 1

        # Count clue types detected
        for clue in data.get("clues_detected", []):
            clue_type = clue.get("clue_type", "unknown")
            error_types_detected[clue_type] += 1

        # Track legacy handler usage
        legacy_handler = data.get("legacy_handler_used")
        if legacy_handler:
            legacy_handler_usage[legacy_handler] += 1

            # Track what errors this legacy handler fixed
            # (when pipeline didn't detect anything)
            if not data.get("clues_detected"):
                error_types_not_detected[legacy_handler].append(json_file)

    # Print results
    print("=" * 80)
    print("PIPELINE PERFORMANCE")
    print("=" * 80)
    print(f"Pipeline successes: {pipeline_successes}")
    print(f"Pipeline failures:  {pipeline_failures}")
    if pipeline_successes + pipeline_failures > 0:
        success_rate = pipeline_successes / (pipeline_successes + pipeline_failures) * 100
        print(f"Success rate:       {success_rate:.1f}%")
    print()

    if failure_reasons:
        print("=" * 80)
        print("FAILURE REASONS (Most Common)")
        print("=" * 80)
        for reason, count in failure_reasons.most_common(5):
            print(f"  [{count}x] {reason}")
        print()

    print("=" * 80)
    print("ERROR TYPES DETECTED BY PIPELINE")
    print("=" * 80)
    if error_types_detected:
        for error_type, count in error_types_detected.most_common():
            print(f"  {error_type:30} : {count:3} times")
    else:
        print("  (none)")
    print()

    print("=" * 80)
    print("LEGACY HANDLERS USED (Most Common First)")
    print("=" * 80)
    if legacy_handler_usage:
        for handler, count in legacy_handler_usage.most_common():
            print(f"  {count:3}x  {handler}")
    else:
        print("  (none - pipeline handled everything!)")
    print()

    print("=" * 80)
    print("MIGRATION PRIORITY RECOMMENDATIONS")
    print("=" * 80)
    if legacy_handler_usage:
        print("Migrate these handlers next (highest impact first):\n")
        for i, (handler, count) in enumerate(legacy_handler_usage.most_common(10), 1):
            print(f"  {i}. {handler}")
            print(f"     Used {count} time(s)")

            # Show example files where this was used
            if handler in error_types_not_detected:
                examples = error_types_not_detected[handler][:3]
                print(f"     Examples: {', '.join(examples)}")
            print()
    else:
        print("No legacy handlers needed - pipeline is handling everything!")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(analyze_legacy_usage())

#!/usr/bin/env python3
"""
Analyze which legacy handlers are being used most frequently.

Usage:
    python3 analyze_legacy_handlers.py

This will scan all .boil/iter*.pipeline.json files and show:
1. Which legacy handlers are used most often
2. Which errors the pipeline successfully handles
3. Migration priority recommendations
"""

import json
import os
import sys
from collections import Counter, defaultdict


def analyze_legacy_usage():
    """Analyze legacy handler usage from JSON debug files"""

    # Find all pipeline JSON files
    boil_dir = ".boil"
    if not os.path.exists(boil_dir):
        print(f"No {boil_dir} directory found. Run boil.py first.")
        return 1

    json_files = [
        f for f in os.listdir(boil_dir)
        if f.endswith(".pipeline.json")
    ]

    if not json_files:
        print(f"No pipeline JSON files found in {boil_dir}")
        return 1

    print(f"Found {len(json_files)} pipeline JSON files\n")

    # Counters
    legacy_handler_usage = Counter()
    pipeline_successes = 0
    pipeline_failures = 0
    error_types_detected = Counter()
    error_types_not_detected = defaultdict(list)

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

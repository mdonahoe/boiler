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

    # New trackers for enhanced output
    all_plans_attempted = []
    files_repaired_by_iteration = {}
    file_line_ratios = {}  # Track line_ratio per file per iteration
    test_command = None

    # Analyze each file
    for json_file in sorted(json_files):
        path = os.path.join(boil_dir, json_file)

        try:
            with open(path, "r") as f:
                data = json.load(f)
        except Exception as e:
            print(f"Warning: Could not read {json_file}: {e}")
            continue

        # Extract iteration number
        iter_match = re.match(r"iter(\d+)\.pipeline\.json", json_file)
        iter_num = int(iter_match.group(1)) if iter_match else None

        # Capture test command (should be same across all iterations)
        if data.get("command") and not test_command:
            test_command = data.get("command")

        # Track files repaired in this iteration
        files_modified = data.get("files_modified", [])
        if files_modified and iter_num is not None:
            files_repaired_by_iteration[iter_num] = files_modified

        # Track line_ratio for partial files
        partial_files = data.get("partial_files", [])
        for pf in partial_files:
            file_name = pf.get("file")
            line_ratio = pf.get("line_ratio")
            if file_name and line_ratio and iter_num is not None:
                if file_name not in file_line_ratios:
                    file_line_ratios[file_name] = {}
                file_line_ratios[file_name][iter_num] = line_ratio

        # Track plans attempted in this iteration
        plans_attempted = data.get("plans_attempted", [])
        for plan in plans_attempted:
            all_plans_attempted.append({
                "iteration": iter_num,
                "plan": plan
            })

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

    # Print test command
    if test_command:
        print("=" * 80)
        print("TEST COMMAND")
        print("=" * 80)
        print(f"  {test_command}")
        print()

    # Print files repaired over the course of boiling
    print("=" * 80)
    print("FILES REPAIRED BY ITERATION")
    print("=" * 80)
    if files_repaired_by_iteration:
        # Collect all unique files
        all_files_repaired = set()
        for iter_num in sorted(files_repaired_by_iteration.keys()):
            files = files_repaired_by_iteration[iter_num]
            for f in files:
                all_files_repaired.add(f)

        # Print iteration-by-iteration with line ratios
        for iter_num in sorted(files_repaired_by_iteration.keys()):
            files = files_repaired_by_iteration[iter_num]

            # For each file, show line ratio if available
            file_info_parts = []
            for f in files:
                if f in file_line_ratios and iter_num in file_line_ratios[f]:
                    line_ratio = file_line_ratios[f][iter_num]

                    # Parse line_ratio to calculate lines added
                    match = re.match(r"(\d+)/(\d+)", line_ratio)
                    if match:
                        current_lines = int(match.group(1))
                        total_lines = int(match.group(2))

                        # Calculate lines added from previous iteration
                        prev_lines = None
                        for prev_iter in range(iter_num - 1, 0, -1):
                            if f in file_line_ratios and prev_iter in file_line_ratios[f]:
                                prev_ratio = file_line_ratios[f][prev_iter]
                                prev_match = re.match(r"(\d+)/(\d+)", prev_ratio)
                                if prev_match:
                                    prev_lines = int(prev_match.group(1))
                                    break

                        if prev_lines is not None:
                            lines_added = current_lines - prev_lines
                            file_info_parts.append(f"{f} ({line_ratio}, +{lines_added} lines)")
                        else:
                            file_info_parts.append(f"{f} ({line_ratio})")
                    else:
                        file_info_parts.append(f"{f} ({line_ratio})")
                else:
                    file_info_parts.append(f)

            print(f"  Iteration {iter_num:2}: {', '.join(file_info_parts)}")

        print()
        print(f"Total unique files repaired: {len(all_files_repaired)}")
        print(f"Files: {', '.join(sorted(all_files_repaired))}")
    else:
        print("  (no files were modified)")
    print()

    # Print all plans attempted
    print("=" * 80)
    print("ALL PLANS ATTEMPTED")
    print("=" * 80)
    if all_plans_attempted:
        print(f"Total plans attempted: {len(all_plans_attempted)}\n")

        # Group by iteration
        for iter_num in sorted(set(p["iteration"] for p in all_plans_attempted if p["iteration"] is not None)):
            iter_plans = [p for p in all_plans_attempted if p["iteration"] == iter_num]
            print(f"Iteration {iter_num}:")
            for p in iter_plans:
                plan = p["plan"]
                plan_type = plan.get("plan_type", "unknown")
                target_file = plan.get("target_file", "unknown")
                action = plan.get("action", "unknown")
                reason = plan.get("reason", "")

                print(f"  - [{plan_type}] {target_file}")
                print(f"    Action: {action}")
                if reason:
                    print(f"    Reason: {reason}")
            print()
    else:
        print("  (no plans were attempted)")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(analyze_legacy_usage())

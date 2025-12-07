"""
Main pipeline orchestration for the 3-stage repair system.

This coordinates the flow: Detection → Planning → Execution
"""

import time
import typing as T
from pipeline.models import GitState, RepairResult
from pipeline.detectors.registry import get_detector_registry
from pipeline.planners.registry import get_planner_registry
from pipeline.executors.registry import get_executor_registry


class Timer:
    def __init__(self):
        self.prev = time.time()
        self.timings = {}

    def __call__(self, name):
        t = time.time()
        dt = t - self.prev
        self.prev = t
        self.timings[name] = dt


def run_pipeline(stderr: str, stdout: str, git_state: GitState, debug: bool = False) -> RepairResult:
    """
    Run the full 3-stage pipeline: Detection → Planning → Execution.

    Now supports multi-fix mode: after a successful plan execution, removes fixed clues
    and continues planning/executing until no clues remain or no plans succeed.

    Args:
        stderr: Standard error output from failed command
        stdout: Standard output from failed command
        git_state: Current git repository state
        debug: If True, print detailed debug information

    Returns:
        RepairResult indicating success/failure
    """
    t = Timer()
    if debug:
        print("=" * 80)
        print("PIPELINE START")
        print("=" * 80)

    # Stage 1: Detection
    if debug:
        print("\n--- STAGE 1: DETECTION ---")
    detector_registry = get_detector_registry()
    all_clues = detector_registry.detect_all(stderr, stdout)

    if not all_clues:
        if debug:
            print("No error clues detected")
        return RepairResult(
            success=False,
            plans_attempted=[],
            files_modified=[],
            error_message="No error clues detected by any detector",
            clues_detected=[],
            plans_generated=[]
        )

    if debug:
        print(f"\nDetected {len(all_clues)} error clue(s):")
        for i, clue in enumerate(all_clues, 1):
            print(f"  {i}. {clue}")

    t("detect_clues")

    # Initialize tracking for multi-fix loop
    remaining_clues = list(all_clues)
    all_plans_generated = []
    all_plans_attempted = []
    all_files_modified = []
    planner_registry = get_planner_registry()
    executor_registry = get_executor_registry()

    # Multi-fix loop: keep planning and executing until no clues remain
    fix_round = 0
    while remaining_clues:
        fix_round += 1
        if debug:
            print(f"\n--- FIX ROUND {fix_round}: {len(remaining_clues)} clue(s) remaining ---")

        # Stage 2: Planning (on remaining clues)
        if debug:
            print("\n--- STAGE 2: PLANNING ---")
        plans = planner_registry.plan_all(remaining_clues, git_state)

        # Initialize clues_fixed for each plan to contain at least the clue_source
        for plan in plans:
            if not plan.clue_source:
                raise ValueError(f"plan {plan} created without a clue!")
            if not plan.clues_fixed:
                plan.clues_fixed = [plan.clue_source]

        t(f"plan_round_{fix_round}")
        if not plans:
            if debug:
                print("No repair plans generated for remaining clues")
            break

        if debug:
            print(f"\nGenerated {len(plans)} repair plan(s) (sorted by priority):")
            for i, plan in enumerate(plans, 1):
                print(f"  {i}. [Priority {plan.priority}] {plan}")
                print(f"      Reason: {plan.reason}")
                print(f"      Fixes {len(plan.clues_fixed)} clue(s)")

        all_plans_generated.extend(plans)

        # Stage 3: Execution (try plans until one succeeds)
        if debug:
            print("\n--- STAGE 3: EXECUTION ---")
        result = executor_registry.execute_plans(plans)
        t(f"exec_round_{fix_round}")

        all_plans_attempted.extend(result.plans_attempted)
        all_files_modified.extend(result.files_modified)

        if not result.success:
            if debug:
                print(f"No plans succeeded in round {fix_round}, stopping")
            break

        # Success! Remove the clues that were fixed by this plan
        if result.plans_attempted:
            successful_plan = result.plans_attempted[-1]  # Last attempted is the successful one
            clues_to_remove = successful_plan.clues_fixed

            if debug:
                print(f"\n[Pipeline] Plan succeeded! Removing {len(clues_to_remove)} fixed clue(s)")

            # Remove fixed clues from remaining_clues
            remaining_clues = [c for c in remaining_clues if c not in clues_to_remove]

            if debug:
                print(f"[Pipeline] {len(remaining_clues)} clue(s) remaining")

    # Determine overall success
    overall_success = len(remaining_clues) < len(all_clues)  # Fixed at least one clue

    if debug:
        print(f"\nFixed {len(all_clues) - len(remaining_clues)} / {len(all_clues)} clue(s)")
        print("=" * 80)
        print("PIPELINE END")
        print("=" * 80)

    return RepairResult(
        success=overall_success,
        plans_attempted=all_plans_attempted,
        files_modified=list(set(all_files_modified)),  # Deduplicate
        error_message=None if overall_success else "Could not fix all clues",
        clues_detected=all_clues,
        plans_generated=all_plans_generated,
        timings=t.timings,
    )


def has_pipeline_handlers() -> bool:
    """
    Check if any handlers are registered in the pipeline.

    Returns:
        True if at least one detector is registered
    """
    detector_registry = get_detector_registry()
    return len(detector_registry.list_detectors()) > 0

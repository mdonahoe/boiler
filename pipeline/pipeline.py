"""
Main pipeline orchestration for the 3-stage repair system.

This coordinates the flow: Detection → Planning → Execution
"""

import typing as T
from pipeline.models import GitState, RepairResult
from pipeline.detectors.registry import get_detector_registry
from pipeline.planners.registry import get_planner_registry
from pipeline.executors.registry import get_executor_registry


def run_pipeline(stderr: str, stdout: str, git_state: GitState, debug: bool = False) -> RepairResult:
    """
    Run the full 3-stage pipeline: Detection → Planning → Execution.

    Args:
        stderr: Standard error output from failed command
        stdout: Standard output from failed command
        git_state: Current git repository state
        debug: If True, print detailed debug information

    Returns:
        RepairResult indicating success/failure
    """
    if debug:
        print("=" * 80)
        print("PIPELINE START")
        print("=" * 80)

    # Stage 1: Detection
    if debug:
        print("\n--- STAGE 1: DETECTION ---")
    detector_registry = get_detector_registry()
    clues = detector_registry.detect_all(stderr, stdout)

    if not clues:
        if debug:
            print("No error clues detected")
        return RepairResult(
            success=False,
            plans_attempted=[],
            files_modified=[],
            error_message="No error clues detected by any detector"
        )

    if debug:
        print(f"\nDetected {len(clues)} error clue(s):")
        for i, clue in enumerate(clues, 1):
            print(f"  {i}. {clue}")

    # Stage 2: Planning
    if debug:
        print("\n--- STAGE 2: PLANNING ---")
    planner_registry = get_planner_registry()
    plans = planner_registry.plan_all(clues, git_state)

    if not plans:
        if debug:
            print("No repair plans generated")
        return RepairResult(
            success=False,
            plans_attempted=[],
            files_modified=[],
            error_message="No repair plans could be generated for detected errors"
        )

    if debug:
        print(f"\nGenerated {len(plans)} repair plan(s) (sorted by priority):")
        for i, plan in enumerate(plans, 1):
            print(f"  {i}. [Priority {plan.priority}] {plan}")
            print(f"      Reason: {plan.reason}")

    # Stage 3: Execution
    if debug:
        print("\n--- STAGE 3: EXECUTION ---")
    executor_registry = get_executor_registry()
    result = executor_registry.execute_plans(plans)

    if debug:
        print(f"\nExecution result: {result}")
        print("=" * 80)
        print("PIPELINE END")
        print("=" * 80)

    return result


def has_pipeline_handlers() -> bool:
    """
    Check if any handlers are registered in the pipeline.

    Returns:
        True if at least one detector is registered
    """
    detector_registry = get_detector_registry()
    return len(detector_registry.list_detectors()) > 0

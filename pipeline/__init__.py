"""
3-stage repair pipeline for boiler.

Usage:
    from pipeline import run_pipeline, GitState
    from pipeline.detectors.registry import register_detector
    from pipeline.planners.registry import register_planner
    from pipeline.executors.registry import register_executor

    # Register your handlers
    register_detector(MyDetector())
    register_planner(MyPlanner())
    register_executor(MyExecutor())

    # Run the pipeline
    git_state = GitState(ref="HEAD", deleted_files=[], git_toplevel="/path")
    result = run_pipeline(stderr, stdout, git_state)
"""

from pipeline.models import ErrorClue, RepairPlan, RepairResult, GitState
from pipeline.pipeline import run_pipeline, has_pipeline_handlers

__all__ = [
    "ErrorClue",
    "RepairPlan",
    "RepairResult",
    "GitState",
    "run_pipeline",
    "has_pipeline_handlers",
]

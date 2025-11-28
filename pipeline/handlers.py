"""
Handler registration for the pipeline.

Import this module to register all detectors, planners, and executors.
"""

from pipeline.detectors.registry import register_detector
from pipeline.planners.registry import register_planner
from pipeline.executors.registry import register_executor

# Import concrete implementations
from pipeline.detectors.permissions import PermissionDeniedDetector
from pipeline.planners.file_restore import PermissionFixPlanner, MissingFilePlanner
from pipeline.executors.git_restore import GitRestoreExecutor


# Track if handlers have been registered
_handlers_registered = False


def register_all_handlers():
    """
    Register all pipeline handlers.

    Call this once at startup to initialize the pipeline.
    """
    global _handlers_registered

    # Only register once
    if _handlers_registered:
        return

    # Register detectors
    register_detector(PermissionDeniedDetector())

    # Register planners
    register_planner(PermissionFixPlanner())
    register_planner(MissingFilePlanner())

    # Register executors
    register_executor(GitRestoreExecutor())

    _handlers_registered = True

    print("[Pipeline] Registered handlers:")
    from pipeline.detectors.registry import get_detector_registry
    from pipeline.planners.registry import get_planner_registry
    from pipeline.executors.registry import get_executor_registry

    print(f"  Detectors: {get_detector_registry().list_detectors()}")
    print(f"  Planners: {get_planner_registry().list_planners()}")
    print(f"  Executors: {get_executor_registry().list_executors()}")

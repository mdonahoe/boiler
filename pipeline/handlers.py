"""
Handler registration for the pipeline.

Import this module to register all detectors, planners, and executors.
"""

from pipeline.detectors.registry import register_detector
from pipeline.planners.registry import register_planner
from pipeline.executors.registry import register_executor

# Import concrete implementations
from pipeline.detectors.permissions import PermissionDeniedDetector
from pipeline.detectors.make_errors import MakeMissingTargetDetector, MakeNoRuleDetector
from pipeline.detectors.file_errors import (
    FopenNoSuchFileDetector,
    FileNotFoundDetector,
    ShellCannotOpenDetector,
    ShellCommandNotFoundDetector,
    CatNoSuchFileDetector,
    DiffNoSuchFileDetector,
    CCompilationErrorDetector,
    CLinkerErrorDetector,
)
from pipeline.detectors.python_code import MissingPythonCodeDetector, PythonNameErrorDetector
from pipeline.planners.file_restore import PermissionFixPlanner, MissingFilePlanner, LinkerUndefinedSymbolsPlanner
from pipeline.planners.make_restore import MakeMissingTargetPlanner, MakeNoRulePlanner
from pipeline.planners.python_code_restore import MissingPythonCodePlanner, PythonNameErrorPlanner
from pipeline.executors.git_restore import GitRestoreExecutor
from pipeline.executors.python_code_restore import PythonCodeRestoreExecutor


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
    register_detector(MakeMissingTargetDetector())
    register_detector(MakeNoRuleDetector())
    register_detector(MissingPythonCodeDetector())
    register_detector(PythonNameErrorDetector())
    register_detector(FopenNoSuchFileDetector())
    register_detector(FileNotFoundDetector())
    register_detector(ShellCannotOpenDetector())
    register_detector(ShellCommandNotFoundDetector())
    register_detector(CatNoSuchFileDetector())
    register_detector(DiffNoSuchFileDetector())
    register_detector(CLinkerErrorDetector())
    register_detector(CCompilationErrorDetector())

    # Register planners
    register_planner(PermissionFixPlanner())
    register_planner(MissingFilePlanner())
    register_planner(LinkerUndefinedSymbolsPlanner())
    register_planner(MakeMissingTargetPlanner())
    register_planner(MakeNoRulePlanner())
    register_planner(MissingPythonCodePlanner())
    register_planner(PythonNameErrorPlanner())

    # Register executors
    register_executor(PythonCodeRestoreExecutor())
    register_executor(GitRestoreExecutor())

    _handlers_registered = True

    print("[Pipeline] Registered handlers:")
    from pipeline.detectors.registry import get_detector_registry
    from pipeline.planners.registry import get_planner_registry
    from pipeline.executors.registry import get_executor_registry

    print(f"  Detectors: {get_detector_registry().list_detectors()}")
    print(f"  Planners: {get_planner_registry().list_planners()}")
    print(f"  Executors: {get_executor_registry().list_executors()}")

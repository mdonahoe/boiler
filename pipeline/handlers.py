"""
Handler registration for the pipeline.

Import this module to register all detectors, planners, and executors.
"""

from pipeline.detectors.registry import register_detector
from pipeline.planners.registry import register_planner
from pipeline.executors.registry import register_executor

# Import concrete implementations
from pipeline.detectors.permissions import PermissionDeniedDetector
from pipeline.detectors.make_errors import (
    MakeEnteringDirectoryDetector,
    MakeMissingTargetDetector,
    MakeNoRuleDetector,
    MakeGlobPatternErrorDetector,
)
from pipeline.detectors.file_errors import (
    FopenNoSuchFileDetector,
    FileNotFoundDetector,
    ShellCannotOpenDetector,
    CannotOpenFileDetector,
    ShellCommandNotFoundDetector,
    CatNoSuchFileDetector,
    DiffNoSuchFileDetector,
    CCompilationErrorDetector,
    CLinkerErrorDetector,
    CIncompleteTypeDetector,
    CImplicitDeclarationDetector,
    CUndeclaredIdentifierDetector,
)
from pipeline.detectors.python_code import MissingPythonCodeDetector, PythonNameErrorDetector
from pipeline.detectors.test_failures import TestFailureDetector
from pipeline.planners.permission_fix import PermissionFixPlanner
from pipeline.planners.missing_file import MissingFilePlanner
from pipeline.planners.linker_undefined_symbols import LinkerUndefinedSymbolsPlanner
from pipeline.planners.missing_directory import MissingDirectoryPlanner
from pipeline.planners.make_missing_target import MakeMissingTargetPlanner
from pipeline.planners.make_no_rule import MakeNoRulePlanner
from pipeline.planners.missing_python_code import MissingPythonCodePlanner
from pipeline.planners.python_name_error import PythonNameErrorPlanner
from pipeline.planners.missing_c_include import MissingCIncludePlanner
from pipeline.planners.missing_c_function import MissingCFunctionPlanner
from pipeline.planners.test_failures import TestFailurePlanner
from pipeline.executors.git_restore import GitRestoreExecutor
from pipeline.executors.python_code_restore import PythonCodeRestoreExecutor
from pipeline.executors.c_code_restore import CCodeRestoreExecutor


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
    register_detector(MakeEnteringDirectoryDetector())
    register_detector(MakeMissingTargetDetector())
    register_detector(MakeNoRuleDetector())
    register_detector(MakeGlobPatternErrorDetector())
    register_detector(MissingPythonCodeDetector())
    register_detector(PythonNameErrorDetector())
    register_detector(FopenNoSuchFileDetector())
    register_detector(FileNotFoundDetector())
    register_detector(ShellCannotOpenDetector())
    register_detector(CannotOpenFileDetector())
    register_detector(ShellCommandNotFoundDetector())
    register_detector(CatNoSuchFileDetector())
    register_detector(DiffNoSuchFileDetector())
    register_detector(CLinkerErrorDetector())
    register_detector(CCompilationErrorDetector())
    register_detector(CIncompleteTypeDetector())
    register_detector(CImplicitDeclarationDetector())
    register_detector(CUndeclaredIdentifierDetector())
    register_detector(TestFailureDetector())

    # Register planners
    register_planner(PermissionFixPlanner())
    register_planner(MissingDirectoryPlanner())
    register_planner(MissingFilePlanner())
    register_planner(LinkerUndefinedSymbolsPlanner())
    register_planner(MakeMissingTargetPlanner())
    register_planner(MakeNoRulePlanner())
    register_planner(MissingPythonCodePlanner())
    register_planner(PythonNameErrorPlanner())
    register_planner(MissingCIncludePlanner())
    register_planner(MissingCFunctionPlanner())
    register_planner(TestFailurePlanner())

    # Register executors
    register_executor(PythonCodeRestoreExecutor())
    register_executor(CCodeRestoreExecutor())
    register_executor(GitRestoreExecutor())

    _handlers_registered = True

"""
Handler registration for the pipeline.

Import this module to register all detectors, planners, and executors.
"""

from src.pipeline.detectors.registry import register_detector
from src.pipeline.planners.registry import register_planner
from src.pipeline.executors.registry import register_executor

# Import concrete implementations
from src.pipeline.detectors.permissions import PermissionDeniedDetector
from src.pipeline.detectors.make_entering_directory import MakeEnteringDirectoryDetector
from src.pipeline.detectors.make_missing_target import MakeMissingTargetDetector
from src.pipeline.detectors.make_no_rule import MakeNoRuleDetector
from src.pipeline.detectors.make_glob_pattern_error import MakeGlobPatternErrorDetector
from src.pipeline.detectors.fopen_no_such_file import FopenNoSuchFileDetector
from src.pipeline.detectors.file_not_found import FileNotFoundDetector
from src.pipeline.detectors.shell_cannot_open import ShellCannotOpenDetector
from src.pipeline.detectors.cannot_open_file import CannotOpenFileDetector
from src.pipeline.detectors.shell_command_not_found import ShellCommandNotFoundDetector
from src.pipeline.detectors.cat_no_such_file import CatNoSuchFileDetector
from src.pipeline.detectors.diff_no_such_file import DiffNoSuchFileDetector
from src.pipeline.detectors.c_compilation_error import CCompilationErrorDetector
from src.pipeline.detectors.c_linker_error import CLinkerErrorDetector
from src.pipeline.detectors.c_incomplete_type import CIncompleteTypeDetector
from src.pipeline.detectors.c_implicit_declaration import CImplicitDeclarationDetector
from src.pipeline.detectors.c_undeclared_identifier import CUndeclaredIdentifierDetector
from src.pipeline.detectors.c_syntax_error import CSyntaxErrorDetector
from src.pipeline.detectors.python_name_error import PythonNameErrorDetector
from src.pipeline.detectors.test_failures import TestFailureDetector
from src.pipeline.planners.permission_fix import PermissionFixPlanner
from src.pipeline.planners.missing_file import MissingFilePlanner
from src.pipeline.planners.linker_undefined_symbols import LinkerUndefinedSymbolsPlanner
from src.pipeline.planners.missing_directory import MissingDirectoryPlanner
from src.pipeline.planners.make_missing_target import MakeMissingTargetPlanner
from src.pipeline.planners.make_no_rule import MakeNoRulePlanner
from src.pipeline.planners.python_name_error import PythonNameErrorPlanner
from src.pipeline.planners.missing_c_include import MissingCIncludePlanner
from src.pipeline.planners.missing_c_function import MissingCFunctionPlanner
from src.pipeline.planners.c_syntax_error import CSyntaxErrorPlanner
from src.pipeline.planners.test_failures import TestFailurePlanner
from src.pipeline.executors.git_restore import GitRestoreExecutor
from src.pipeline.executors.python_code_restore import PythonCodeRestoreExecutor
from src.pipeline.executors.c_code_restore import CCodeRestoreExecutor


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
    register_detector(CSyntaxErrorDetector())
    register_detector(TestFailureDetector())

    # Register planners
    register_planner(PermissionFixPlanner())
    register_planner(MissingDirectoryPlanner())
    register_planner(MissingFilePlanner())
    register_planner(LinkerUndefinedSymbolsPlanner())
    register_planner(MakeMissingTargetPlanner())
    register_planner(MakeNoRulePlanner())
    register_planner(PythonNameErrorPlanner())
    register_planner(MissingCIncludePlanner())
    register_planner(MissingCFunctionPlanner())
    register_planner(CSyntaxErrorPlanner())
    register_planner(TestFailurePlanner())

    # Register executors
    register_executor(PythonCodeRestoreExecutor())
    register_executor(CCodeRestoreExecutor())
    register_executor(GitRestoreExecutor())

    _handlers_registered = True

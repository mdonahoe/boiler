"""
Handler registration for the pipeline.

Import this module to register all detectors, planners, and executors.
"""

from pipeline.detectors.registry import register_detector
from pipeline.planners.registry import register_planner
from pipeline.executors.registry import register_executor

# Import concrete implementations
from pipeline.detectors.permissions import PermissionDeniedDetector
from pipeline.detectors.make_entering_directory import MakeEnteringDirectoryDetector
from pipeline.detectors.make_missing_target import MakeMissingTargetDetector
from pipeline.detectors.make_no_rule import MakeNoRuleDetector
from pipeline.detectors.make_glob_pattern_error import MakeGlobPatternErrorDetector
from pipeline.detectors.fopen_no_such_file import FopenNoSuchFileDetector
from pipeline.detectors.file_not_found import FileNotFoundDetector
from pipeline.detectors.shell_cannot_open import ShellCannotOpenDetector
from pipeline.detectors.cannot_open_file import CannotOpenFileDetector
from pipeline.detectors.shell_command_not_found import ShellCommandNotFoundDetector
from pipeline.detectors.cat_no_such_file import CatNoSuchFileDetector
from pipeline.detectors.diff_no_such_file import DiffNoSuchFileDetector
from pipeline.detectors.c_compilation_error import CCompilationErrorDetector
from pipeline.detectors.c_linker_error import CLinkerErrorDetector
from pipeline.detectors.c_incomplete_type import CIncompleteTypeDetector
from pipeline.detectors.c_implicit_declaration import CImplicitDeclarationDetector
from pipeline.detectors.c_undeclared_identifier import CUndeclaredIdentifierDetector
from pipeline.detectors.c_syntax_error import CSyntaxErrorDetector
from pipeline.detectors.python_name_error import PythonNameErrorDetector
from pipeline.detectors.test_failures import TestFailureDetector
from pipeline.planners.permission_fix import PermissionFixPlanner
from pipeline.planners.missing_file import MissingFilePlanner
from pipeline.planners.linker_undefined_symbols import LinkerUndefinedSymbolsPlanner
from pipeline.planners.missing_directory import MissingDirectoryPlanner
from pipeline.planners.make_missing_target import MakeMissingTargetPlanner
from pipeline.planners.make_no_rule import MakeNoRulePlanner
from pipeline.planners.python_name_error import PythonNameErrorPlanner
from pipeline.planners.missing_c_include import MissingCIncludePlanner
from pipeline.planners.missing_c_function import MissingCFunctionPlanner
from pipeline.planners.c_syntax_error import CSyntaxErrorPlanner
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

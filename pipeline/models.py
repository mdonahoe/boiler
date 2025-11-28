"""
Core data models for the 3-stage repair pipeline.

Stage 1: Detectors produce ErrorClue objects
Stage 2: Planners convert ErrorClue objects into RepairPlan objects
Stage 3: Executors execute RepairPlan objects and return RepairResult objects
"""

import dataclasses
import typing as T


@dataclasses.dataclass
class ErrorClue:
    """
    Evidence of a specific error type found in stderr/stdout.

    Produced by Stage 1 (Detection).
    """
    clue_type: str  # e.g., "permission_error", "missing_file", "name_error"
    confidence: float  # 0.0-1.0, how confident we are this is the right error
    context: T.Dict[str, str]  # extracted details (file_path, symbol_name, etc.)
    source_line: str  # the actual error line that triggered this clue

    def __repr__(self) -> str:
        return f"ErrorClue(type={self.clue_type}, confidence={self.confidence}, context={self.context})"


@dataclasses.dataclass
class RepairPlan:
    """
    A proposed fix for an error.

    Produced by Stage 2 (Planning).
    """
    plan_type: str  # "restore_file", "repair_symbol", "restore_permissions"
    priority: int  # Lower = higher priority (0 = must fix first)
    target_file: str  # file to modify (relative to cwd)
    action: str  # "restore_full", "restore_symbol", "restore_permissions"
    params: T.Dict[str, T.Any]  # action-specific parameters
    reason: str  # human-readable explanation
    clue_source: ErrorClue  # the clue that generated this plan

    def __repr__(self) -> str:
        return f"RepairPlan(type={self.plan_type}, priority={self.priority}, action={self.action}, target={self.target_file})"


@dataclasses.dataclass
class RepairResult:
    """
    The outcome of attempting repairs.

    Produced by Stage 3 (Execution).
    """
    success: bool
    plans_attempted: T.List[RepairPlan]
    files_modified: T.List[str]
    error_message: T.Optional[str]
    # Debug information
    clues_detected: T.Optional[T.List[ErrorClue]] = None
    plans_generated: T.Optional[T.List[RepairPlan]] = None

    def __repr__(self) -> str:
        status = "SUCCESS" if self.success else "FAILED"
        return f"RepairResult({status}, modified={len(self.files_modified)} files)"

    def to_dict(self) -> T.Dict[str, T.Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "success": self.success,
            "files_modified": self.files_modified,
            "error_message": self.error_message,
            "clues_detected": [
                {
                    "clue_type": c.clue_type,
                    "confidence": c.confidence,
                    "context": c.context,
                    "source_line": c.source_line
                }
                for c in (self.clues_detected or [])
            ],
            "plans_generated": [
                {
                    "plan_type": p.plan_type,
                    "priority": p.priority,
                    "target_file": p.target_file,
                    "action": p.action,
                    "params": p.params,
                    "reason": p.reason
                }
                for p in (self.plans_generated or [])
            ],
            "plans_attempted": [
                {
                    "plan_type": p.plan_type,
                    "priority": p.priority,
                    "target_file": p.target_file,
                    "action": p.action,
                    "reason": p.reason
                }
                for p in self.plans_attempted
            ]
        }


@dataclasses.dataclass
class GitState:
    """
    Helper class to encapsulate git repository state.
    """
    ref: str  # git ref to restore from (e.g., "HEAD")
    deleted_files: T.Set[str]  # files deleted in working directory
    git_toplevel: str  # git repository root directory

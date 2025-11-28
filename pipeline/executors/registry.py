"""
Registry for managing all repair executors.
"""

import typing as T
from pipeline.executors.base import Executor
from pipeline.models import RepairPlan, RepairResult


class ExecutorRegistry:
    """
    Central registry for all repair executors.

    Manages registration and execution of executors.
    """

    def __init__(self):
        self._executors: T.List[Executor] = []

    def register(self, executor: Executor) -> None:
        """Register a new executor"""
        self._executors.append(executor)

    def execute_plans(self, plans: T.List[RepairPlan]) -> RepairResult:
        """
        Execute repair plans in order until one succeeds or all fail.

        Args:
            plans: List of RepairPlan objects, assumed to be sorted by priority

        Returns:
            RepairResult for the first successful plan, or combined result if all fail
        """
        if not plans:
            return RepairResult(
                success=False,
                plans_attempted=[],
                files_modified=[],
                error_message="No plans to execute"
            )

        all_attempted = []
        all_modified = []

        for plan in plans:
            # Find executor that can handle this action
            executor = self._find_executor(plan.action)
            if not executor:
                print(f"[Executor] No executor found for action: {plan.action}")
                continue

            # Validate plan
            is_valid, error_msg = executor.validate_plan(plan)
            if not is_valid:
                print(f"[Executor:{executor.name}] Plan validation failed: {error_msg}")
                continue

            # Execute plan
            try:
                print(f"[Executor:{executor.name}] Executing: {plan.action} on {plan.target_file}")
                result = executor.execute(plan)
                all_attempted.append(plan)
                all_modified.extend(result.files_modified)

                if result.success:
                    # Success! Return immediately
                    return RepairResult(
                        success=True,
                        plans_attempted=all_attempted,
                        files_modified=all_modified,
                        error_message=None
                    )
                else:
                    print(f"[Executor:{executor.name}] Failed: {result.error_message}")
            except Exception as e:
                print(f"[Executor:{executor.name}] Exception: {e}")
                # Continue with next plan

        # All plans failed
        return RepairResult(
            success=False,
            plans_attempted=all_attempted,
            files_modified=all_modified,
            error_message="All repair plans failed"
        )

    def _find_executor(self, action: str) -> T.Optional[Executor]:
        """Find an executor that can handle the given action"""
        for executor in self._executors:
            if executor.can_handle(action):
                return executor
        return None

    def list_executors(self) -> T.List[str]:
        """Return list of registered executor names"""
        return [e.name for e in self._executors]


# Global registry instance
_registry = ExecutorRegistry()


def register_executor(executor: Executor) -> None:
    """Register an executor with the global registry"""
    _registry.register(executor)


def get_executor_registry() -> ExecutorRegistry:
    """Get the global executor registry"""
    return _registry

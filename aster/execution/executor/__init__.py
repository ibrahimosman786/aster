"""Backend-neutral worker launch, control RPC, and result handling.

Executors coordinate workers; tensor collectives and checkpoint semantics stay
with the training or serving backend. Importing this package does not load Ray.
"""

from aster.execution.executor.base import Executor, ExecutorConfig, ExecutorFuture, WorkerSpec, resolve
from aster.execution.executor.failure import ExecutorFailedError, ExecutorFailure, ExecutorFailureListener
from aster.execution.executor.requirements import ExecutionRequirements

__all__ = [
    "ExecutionRequirements",
    "Executor",
    "ExecutorConfig",
    "ExecutorFailedError",
    "ExecutorFailure",
    "ExecutorFailureListener",
    "ExecutorFuture",
    "WorkerSpec",
    "resolve",
]

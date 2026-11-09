"""Resolve Slime launcher aliases before allocating model resources."""

from __future__ import annotations

from aster.execution.executor import Executor
from aster.execution.executor.config import ExecutorSettings, select_executor

DEFAULT_EXECUTOR_BACKEND = "aster.train.slime_backend.aster_adapters.executors.ray:SlimeRayExecutor"


def slime_executor_class(backend: str | type[Executor] | None) -> type[Executor]:
    if isinstance(backend, type):
        return Executor.get_class(backend)
    selected = select_executor(ExecutorSettings(backend or "auto"), role="training").settings.backend
    if selected in ("mp", "uni"):
        raise ValueError(
            f"Slime training requires ray or a Slime-compatible executor; {selected!r} is not a GPU launcher"
        )
    if selected == "ray":
        selected = DEFAULT_EXECUTOR_BACKEND
    return Executor.get_class(selected)

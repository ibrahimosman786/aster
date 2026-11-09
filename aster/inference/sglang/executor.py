"""Default SGLang rollout executor, with all SGLang serving ownership here."""

from __future__ import annotations

from aster.inference.engine_control import EngineExecutor


class SGLangExecutor(EngineExecutor):
    """One control rank manages multi-node SGLang engine groups."""

    def create_worker(self) -> object:
        from aster.inference.sglang.worker import SGLangWorker

        return SGLangWorker(**dict(self.config.options))

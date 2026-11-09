"""Native vLLM inference backend: the engine operations that Aster's serving runtimes call."""

from __future__ import annotations

from aster.inference.engine_control import EngineInferenceBackend


class VLLMInferenceBackend(EngineInferenceBackend):
    """Translate the serving runtime's operations to the vLLM control vocabulary."""

    engine_name = "vLLM"

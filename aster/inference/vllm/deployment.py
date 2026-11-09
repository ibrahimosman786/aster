"""Construct vLLM inference from resolved deployment input values."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from aster.inference.engine_control import engine_executor_class
from aster.inference.vllm.config import VLLMConfig
from aster.inference.vllm.control import VLLMExecutor
from aster.inference.vllm.service import VLLMInferenceService


def create_inference(config: Mapping[str, Any]) -> VLLMInferenceService:
    """Validate native settings before allocation and return an unstarted service."""
    values = dict(config)
    values["executor"] = engine_executor_class(values.get("executor", "auto"), VLLMExecutor, "vLLM")
    return VLLMInferenceService(VLLMConfig(**values))

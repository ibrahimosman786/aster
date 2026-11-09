"""Megatron-Bridge model bridges for the layouts slime actually builds.

Aster exports adapters through Megatron-Bridge's ``AutoBridge``; Bridge picks
the bridge by the HF architecture name and assumes the Megatron model has the
parameter layout of Bridge's own provider for that architecture. Models that
slime builds through ``slime_plugins`` (Qwen3.5's hybrid GatedDeltaNet layout)
use a different layout, so Aster registers its own bridges for them. Registration
is idempotent and must run before ``AutoBridge.from_hf_pretrained``.
"""

from __future__ import annotations

from aster.train.slime_backend.aster_adapters.megatron.bridges.qwen3_5 import register_slime_qwen35_bridge


def register_aster_model_bridges() -> None:
    """Register every Aster-owned model bridge with Megatron-Bridge's dispatch."""

    register_slime_qwen35_bridge()


__all__ = ["register_aster_model_bridges", "register_slime_qwen35_bridge"]

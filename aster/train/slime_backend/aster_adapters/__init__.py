"""Adapters between the Slime training component and Slime's workers.

``aster.train.slime_backend.component`` runs each training job and saves its
checkpoints. These adapters supply Slime's arguments, sample packing,
optimizer execution and checkpoint storage. Inference adapters live in
``aster.inference`` and are assembled independently by Aster.
"""

from aster.train.slime_backend.aster_adapters.training_job.storage import RetentionConfig

__all__ = ["RetentionConfig"]

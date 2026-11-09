"""SGLang inference control actor, independent of the training backend.

Engine handles travel through control RPCs; weights reach the engines as
files that the engines read themselves.
"""

from __future__ import annotations

from aster.inference.engine_control import EngineControl
from aster.inference.sglang.config import SGLangConfig


class SGLangControl(EngineControl[SGLangConfig]):
    """Own the SGLang serving executor inside Aster's inference control actor."""

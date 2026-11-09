"""Control integrations must implement the complete inherited interface."""

import pytest

from aster.execution.executor.failure import ExecutorFailureListener
from aster.inference.interfaces import AdapterEngine, InferenceBackend, InferenceEngine
from aster.inference.recovery import EngineHealthChecks, EngineHealthTarget, InferenceEngineGroup, InferenceMonitor
from aster.inference.sglang.engine import AsterSGLangEngine
from aster.inference.vllm.engine import AsterVLLMEngine


@pytest.mark.parametrize(
    "interface",
    [
        InferenceEngineGroup,
        InferenceMonitor,
        EngineHealthChecks,
        EngineHealthTarget,
        InferenceBackend,
        InferenceEngine,
        AdapterEngine,
        ExecutorFailureListener,
    ],
)
def test_incomplete_control_integration_cannot_be_constructed(interface):
    class IncompleteIntegration(interface):
        pass

    with pytest.raises(TypeError, match="abstract"):
        IncompleteIntegration()


@pytest.mark.parametrize("engine_type", [AsterSGLangEngine, AsterVLLMEngine])
def test_native_engines_implement_the_whole_engine_vocabulary(engine_type):
    assert issubclass(engine_type, InferenceEngine)
    assert not engine_type.__abstractmethods__

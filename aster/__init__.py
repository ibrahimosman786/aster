"""Aster: continual learning infra for self-improving agents.

``aster`` holds every shared mechanism
(records, service, runtime, scenario, artifacts and their components, the training
loop with the candidate evaluation a recipe configures, and the recipe
contract a method implements). Learning methods are separate packages selected
through dotted class references; importing ``aster`` never imports method code.
The repository's sibling ``recipes`` tree is a cookbook and is not part of the
installed Aster package.
"""

import os

for name, value in list(os.environ.items()):
    if name.startswith("REEF_"):
        os.environ.setdefault("ASTER_" + name[len("REEF_") :], value)

# isort: skip_file
from aster.core.version import __version__

from aster.core import AsterError, RequestType, AgentRecord, ReportBase, ReportValidationError
from aster.service.wire import ReportPayload, RequestHeaders, parse_request_headers
from aster.storage.records import RecordStore
from aster.evaluation import (
    ActivationRule,
    AlwaysSelectMixin,
    CandidateEvaluationPlugin,
    CandidateEvaluator,
    CandidateSelector,
    EvaluationResult,
    MadeArtifact,
    RegressionCheckMixin,
    SelectionDecision,
    UpdateCandidate,
)
from aster.storage.commits import SCENARIO_METADATA_KEY
from aster.scenario import Scenario
from aster.recipe import (
    RecipeConfigError,
    Recipe,
)
from aster.dispatcher import Dispatcher, build_default_dispatcher
from aster.train import Sample2Job, Trainer, TrainingPipeline
from aster.inference.interfaces import InferenceRuntime
from aster.train.component import TrainingComponent, TrainingJob

__all__ = [
    "SCENARIO_METADATA_KEY",
    "ActivationRule",
    "AgentRecord",
    "AlwaysSelectMixin",
    "CandidateEvaluationPlugin",
    "CandidateEvaluator",
    "CandidateSelector",
    "Dispatcher",
    "EvaluationResult",
    "InferenceRuntime",
    "MadeArtifact",
    "Recipe",
    "RecipeConfigError",
    "RecordStore",
    "AsterError",
    "RegressionCheckMixin",
    "ReportBase",
    "ReportPayload",
    "ReportValidationError",
    "RequestHeaders",
    "RequestType",
    "Sample2Job",
    "Scenario",
    "SelectionDecision",
    "Trainer",
    "TrainingComponent",
    "TrainingJob",
    "TrainingPipeline",
    "UpdateCandidate",
    "__version__",
    "build_default_dispatcher",
    "parse_request_headers",
]

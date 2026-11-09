"""Candidate evaluation and the activation rules: contracts, built-ins, and plugin loading.

A harness recipe builds a publication policy from ``evolution.evaluation``, a
:class:`CandidateEvaluationPlugin`. :class:`aster.train.Trainer` runs it between
prepare and settle to decide which candidate tree the search keeps. The activation rule decides whether an
artifact that training makes serves; ``activation`` holds the built-in rules
(``always``, ``never`` and ``evaluated``). The shared contracts live in
``aster.core.evaluation`` and ``aster.core.activation``. This package owns the
built-in evaluators, selectors and rules.

``harness`` measures harness candidates by running evaluation rollouts. It
holds ``HarnessCandidate``, its evaluator ``HarnessTaskEvaluator``, the
``TaskScorer`` contract that a deployment names, the history that is the
score cache, and the ``compare``, ``floor`` and ``none`` publication policies.
``rollout_worker`` runs the rollouts of an artifact evaluation, and
``artifact_endpoint`` answers their model calls from the evaluated artifact.
"""

from aster.core.activation import ActivationRule, MadeArtifact
from aster.core.evaluation import (
    CandidateEvaluationPlugin,
    CandidateEvaluator,
    CandidateSelector,
    EvaluationResult,
    SelectionDecision,
    UpdateCandidate,
)
from aster.evaluation.activation import AlwaysActivate, EvaluatedActivation, NeverActivate
from aster.evaluation.evaluators import AlwaysSelectMixin, RegressionCheckMixin

__all__ = [
    "ActivationRule",
    "AlwaysActivate",
    "AlwaysSelectMixin",
    "CandidateEvaluationPlugin",
    "CandidateEvaluator",
    "CandidateSelector",
    "EvaluatedActivation",
    "EvaluationResult",
    "MadeArtifact",
    "NeverActivate",
    "RegressionCheckMixin",
    "SelectionDecision",
    "UpdateCandidate",
]

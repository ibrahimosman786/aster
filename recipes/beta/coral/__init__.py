"""CORAL test-time training through Aster: one method, one package.

- ``middleware`` — the ASGI layer that stamps Aster scenario/tag headers onto
  CORAL gateway traffic and captures Aster receipts.
- ``journal`` — the append-only call journal correlation reads.
- ``reporter`` — finalized CORAL attempts posted to ``/aster/report``.
- ``watcher`` — CORAL's on-disk attempt records, reported exactly once each.
- ``processor``/``recipe`` — sibling groups as grouped relative-reward
  training units, reusing the tttd objective and loss family.
- ``bundle`` — the run's result bundle, derived from journal + reports.
- ``gateway_launcher`` — splices the middleware under CORAL's gateway (a
  ``GatewayManager`` the caller owns, or the one ``AgentManager`` builds).

The runnable example lives in ``examples/coral_demo``.
"""

from recipes.beta.coral.journal import CallJournal, CallRecord
from recipes.beta.coral.middleware import AsterGatewayMiddleware
from recipes.beta.coral.recipe import CoralRecipe
from recipes.beta.coral.reporter import AttemptReport, report_attempt
from recipes.beta.coral.watcher import AttemptWatcher, FinalizedAttempt

__all__ = [
    "AttemptReport",
    "AttemptWatcher",
    "CallJournal",
    "CallRecord",
    "CoralRecipe",
    "FinalizedAttempt",
    "AsterGatewayMiddleware",
    "report_attempt",
]

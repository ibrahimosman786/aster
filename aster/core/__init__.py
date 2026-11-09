"""Shared value types, contracts, and root errors: the bottom of the dependency graph.

``config`` holds field declarations and value parsing shared by service,
recipe and runtime components; it does not discover or import components.

Nothing here implements storage behavior or I/O. Record storage interfaces
belong to ``aster.storage.records``; concrete record and artifact adapters build on the
shared identities and wire types defined here.

The admission bar is concrete: a type belongs here only when at least two
packages that do not depend on each other need it, and it carries no I/O.
``job_data`` and ``evaluation`` hold the values and candidate contracts shared
by runtimes and training; ``weight_layout`` holds the values that
``aster.train`` and ``aster.inference`` both read; ``requirements`` validates training-request requirements
and reads their release-chain records.
``training_request`` validates TRAIN bodies at admission and holds the queued
request carried by a job's data.
Anything with one consumer stays in that consumer — the ``x-aster-*`` header
parsing and the HTTP report envelope live in ``service/wire.py`` — while the
typed report *body* is ``reports/`` here because four packages parse it.

The boundary is directional: core imports nothing above it. In particular
``aster.core`` never imports ``aster.artifact`` — ``snapshot`` lives here
so storage locators can be shared without pulling in backend implementations, and
``artifacts/artifact.py`` re-exports it. Pinned by
``tests/contributing/test_dependency_boundaries.py``.
"""

from aster.core.errors import AsterError, UnknownScenario
from aster.core.records_types import AgentRecord, RequestType
from aster.core.reports import ReportBase, ReportValidationError
from aster.core.snapshot import SnapshotRef

__all__ = [
    "AgentRecord",
    "AsterError",
    "ReportBase",
    "ReportValidationError",
    "RequestType",
    "SnapshotRef",
    "UnknownScenario",
]

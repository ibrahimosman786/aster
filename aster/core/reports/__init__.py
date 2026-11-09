"""Typed report contracts: the schema of the feedback a harness sends.

A report is the second thing a harness sends Aster, after the inference it
refers to (``AgentRecord``); both live in ``core`` because the service
validates a report at ingress, the scenario binds its type, the recipe
declares it, and the processors rehydrate it — packages that do not depend
on each other. ``ReportBase`` is the contract; ``ScoredRolloutReport`` is
the shared score-only vocabulary and ``TeacherContextReport`` the shared
vocabulary of the distilling recipes (a rollout and the text its teacher
sees); method-specific contracts live with their method packages.
"""

from aster.core.reports.base import ReportBase, ReportValidationError, validate_report_payload
from aster.core.reports.scored_rollout import ScoredRolloutReport
from aster.core.reports.teacher_context import TeacherContextReport

__all__ = [
    "ReportBase",
    "ReportValidationError",
    "ScoredRolloutReport",
    "TeacherContextReport",
    "validate_report_payload",
]

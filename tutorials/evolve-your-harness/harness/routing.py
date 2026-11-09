"""A controlled example of learning an organization-specific routing convention."""

import json

from reef.evaluation.harness import TaskScorer
from reef.harness.tasks.trajectory import final_assistant_text


def task(region: str, tier: str, urgent: bool) -> str:
    payload = json.dumps(dict(region=region, tier=tier, urgent=urgent))
    return (
        "Route this support request using our organization's internal route-code convention. "
        "Put only the route code on the final line. Request: " + payload
    )


def expected(prompt: str) -> str:
    request = json.loads(prompt.split("Request: ", 1)[1])
    tier = "E" if request["tier"] == "enterprise" else "S"
    urgency = "now" if request["urgent"] else "queue"
    return f"{request['region'].lower()}::{tier}::{urgency}"


def grade(prompt: str, answer: str | None) -> float:
    lines = (answer or "").strip().splitlines()
    return float(bool(lines) and lines[-1].strip() == expected(prompt))


class RoutingScorer(TaskScorer):
    """Grade final route codes against the fixed organization convention."""

    def score(self, task: str, result) -> float:
        return grade(task, final_assistant_text(result.trajectory))

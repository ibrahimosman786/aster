"""Attach a Harbor trial's verifier reward to the Aster inferences that earned it.

The agent hands :func:`post_report` the trial result Harbor wrote: the score is
the verifier reward, the references are the receipts the agent left in the
Harbor agent context.
"""

import uuid
from typing import Any

from reef_client import AsterClient


def post_report(result: dict[str, Any], *, client: AsterClient, scenario: str) -> dict[str, Any]:
    trial_id = result["id"]
    task_name = result["task_name"]
    score = result["verifier_result"]["rewards"]["reward"]
    payload = {
        # A report id derived from the trial makes a duplicate post a no-op on
        # Aster's side, not a second report about the same trial.
        "agent_record_id": uuid.uuid5(uuid.NAMESPACE_URL, f"aster:harbor:{trial_id}").hex,
        "score": score,
        "feedback": f"harbor verifier reward for {task_name}: {score}",
        "references": result["agent_result"]["metadata"]["aster"]["agent_record_ids"],
        "metadata": {"harbor": {"trial_id": trial_id, "task_name": task_name}},
    }
    return client.report(scenario, payload)

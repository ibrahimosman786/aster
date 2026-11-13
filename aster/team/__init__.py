"""A software team that turns one brief into files, a test run, and a review.

A team run is one directory. It holds the brief, the files each specialist wrote,
the pytest output, and ``events.jsonl``. A character state in the workspace is
the latest event for that specialist. The run does not call a model and does
not change model weights.
"""

from aster.team.run import TeamRun, run_software_team

__all__ = ["TeamRun", "run_software_team"]

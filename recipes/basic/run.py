"""The whole loop, in the open.

One rollout:

    solve  — reef-eval runs the harbor/ task under our agent; the agent asks
             Aster for the answer (Aster records the exchange, returns a
             receipt)
    verify — Harbor's isolated verifier scores the attempt
    learn  — the agent reports the verifier score against the receipt;
             Aster trains on it and serves the next version

``Lab.run`` is reef-eval's one primitive: task in, trusted scored row out.
"""

import asyncio
from pathlib import Path

from reef_eval import Lab

MODEL = "gpt-4o"  # provider model the recipe proxies to

HERE = Path(__file__).resolve().parent

lab = Lab(HERE / "work" / "lab")
agent = {"name": "harness:HarborAgent", "model_name": MODEL}
row = asyncio.run(lab.run(str(HERE / "harbor"), agent))
print(f"rollout reward: {row.rewards}")

Quickstart: serve inference and report feedback
===============================================

Start Aster locally, send an inference request through a hosted provider,
report feedback on the response, and inspect the snapshot history. This
quickstart needs no GPU; the final section links to recipes that learn
from the records you collect.

A typical Aster workflow includes the following steps:

1. **Request.** Harness sends a request with a *scenario*.
2. **Response.** Aster forwards the response from the model to the harness, with
   a *receipt* attached to it.
3. **Report.** An entity provides a *report* containing feedback for the
   response associated with the *receipt* to Aster.
4. **Learn.** Aster runs the training / learning process against the reports in
   training jobs according to its *recipe*.
5. **Evolve.** Aster potentially creates a new version of the *artifact*, which
   may become immediately effective (e.g. model evolution) or requires a pull
   from the harness to take effect (e.g. harness evolution).
6. **Update.** Harness can view the history of served artifacts (*release
   chain*) and potentially pull a new harness tree.

This workflow touches a few key concepts:

- **scenario** - A specific type of workload. For example, a code reviewer, or a
  math problem solver. Aster manages the training of each scenario separately,
  i.e. records, training state and snapshot chain.
- **receipt** - The id of a recorded inference exchange. It identifies the
  request, the response, and the snapshot that produced it.
- **report** - A feedback quoting one or more receipts.
- **recipe** - How Aster use the report to evolve new versions of artifacts. A
  deployment serves one recipe, and every scenario on it evolves under that
  recipe.
- **artifact** - The content a snapshot selects: model weights, or a harness
  tree of rules, prompts, skills, and config. Versioned.
- **release** - One accepted publication in a scenario. The chain of them is
  the scenario's history.

We will explore these concepts in greater depth later. For now, it's time to
get our hands dirty and experience these steps ourselves.

Run the loop
------------

This runs the serving half of the loop against a hosted provider, on a laptop,
with no GPU.

.. container:: steps

   #. **Install.** Follow the laptop path in `Installation
      <installation.rst>`__.

   #. **Serve.** Connect an OpenAI-compatible provider and record what it
      serves, without a YAML file or GPU.

      .. code:: bash

         export ASTER_TOKEN=aster-local
         export ASTER_UPSTREAM_API_KEY=sk-...

         aster serve \
           --inference.upstream-url https://api.openai.com \
           --inference.upstream-model gpt-4o

      Aster listens on ``127.0.0.1:8900`` and writes state under ``.aster/`` in
      the directory where you run it. The upstream key and Aster token come
      from the environment. Without ``-c``, no config file is read. To connect
      another provider, change the URL and model. Existing deployments can
      still use ``aster serve -c recipes/basic/external-provider.yaml``.

      ``aster serve`` runs in the foreground and holds the terminal until
      Ctrl-C. Leave it running and open a second terminal for everything below.

      .. code:: bash

         curl -f http://127.0.0.1:8900/healthz     # {"ok": true}

   #. **Create a scenario.** Aster answers inference only for a scenario that
      exists, and a request for an unknown scenario gets HTTP 404.

      .. code:: bash

         curl -sS -X POST http://127.0.0.1:8900/aster/scenarios \
           -H "Authorization: Bearer aster-local" \
           -H "Content-Type: application/json" \
           -d '{"name": "hello-aster"}'

   #. **Send a request and report on it.** The body is the provider's;
      ``x-aster-scenario`` is the only thing Aster adds. The response header
      ``x-aster-agent-record-id`` carries the **receipt**, which names the
      stored exchange. Tests, a verifier, a rubric, a thumbs-down, or any other
      grader you already have can report feedback against it.

      .. code:: python

         import httpx

         client = httpx.Client(
             base_url="http://127.0.0.1:8900",
             headers={"Authorization": "Bearer aster-local", "x-aster-scenario": "hello-aster"},
         )

         response = client.post(
             "/v1/chat/completions",
             json={"model": "gpt-4o", "messages": [{"role": "user", "content": "Return exactly: aster is ready"}]},
         )
         response.raise_for_status()
         receipt = response.headers["x-aster-agent-record-id"]  # e.g. ee5aa401634b4567bf9dae21816abde4
         matched = response.json()["choices"][0]["message"]["content"].strip() == "aster is ready"

         report = client.post(
             "/aster/report",
             json={"score": float(matched), "feedback": "matched" if matched else "wrong answer", "references": [receipt]},
         )
         print(report.json())
         # {"agent_record_id": "cce17dd7...", "scenario": "hello-aster", "request_type": "report"}

      Reports are records too, so the response carries the report's own record
      id. Only inference-record ids are receipts, and they appear only
      in ``references``.

   #. **Or use the wire client.** Install the stdlib-only ``reef-client`` with
      ``pip install reef-client``. It keeps the receipt for you.

      .. code:: python

         from reef_client import AsterClient

         client = AsterClient("http://127.0.0.1:8900", token="aster-local")

         body, receipt = client.inference_with_record(
             "hello-aster",                                   # the scenario
             "/v1/chat/completions",
             {"model": "gpt-4o", "messages": [{"role": "user", "content": "hi"}]},
         )
         answer = body["choices"][0]["message"]["content"]

         # ... whatever already judges your agent decides this score ...
         client.report("hello-aster", {"score": 1.0}, references=[receipt])

      With an OpenAI SDK instead, point ``base_url`` at
      ``http://127.0.0.1:8900/v1``, send ``x-aster-scenario`` as a default
      header, and read ``x-aster-agent-record-id`` off the raw response.

      On the wire it is an ordinary provider request with one added header, and
      the receipt comes back in a response header:

      .. code:: bash

         curl -sS -D - -o /dev/null \
           http://127.0.0.1:8900/v1/chat/completions \
           -H "Authorization: Bearer aster-local" \
           -H "x-aster-scenario: hello-aster" \
           -H "Content-Type: application/json" \
           -d '{"model": "gpt-4o", "messages": [{"role": "user", "content": "hi"}]}'
         # x-aster-agent-record-id: ee5aa401634b4567bf9dae21816abde4

   #. **Read the artifacts.**

      .. code:: bash

         curl -sS -H "Authorization: Bearer aster-local" \
           http://127.0.0.1:8900/aster/scenarios/hello-aster/artifacts
         # {"scenario": "hello-aster", "artifacts": [{"artifact_id": "...", "operation": "creation", "active": true, ...}]}

      One artifact, and it will stay at one: this deployment's recipe is the
      core ``recipe``, which records and trains nothing.

To make the chain advance, bind a recipe that learns. To use a weight recipe,
start from ``recipes/sao/examples/imo_answerbench/serve.yaml``. It selects
``recipe.implementation: recipes.sao.recipe:SAORecipe`` and configures the
Slime training workers and the serving engine.
Weight recipes need GPUs (`Evolve your model
<../user-guide/evolve-your-model.rst>`__).

A harness recipe runs on a laptop with only a model endpoint. Bind
``aster.recipe.harness:HarnessEvolutionRecipe`` and give it a **preset**
naming your method (``evolution.method``), the seed tree, and the evaluation's
tasks and scorer (``evolution.evaluation``). ``tutorials/evolve-your-harness/run.sh`` wires the whole loop
together. Run it, then read `Evolve your harness
<../user-guide/evolve-your-harness.rst>`__ for an explanation of each piece.

Choose your next step
---------------------

- `Compare learning recipes <../user-guide/recipes.rst>`__ to choose between
  model training and harness evolution based on the feedback you have.
- Try `GEPA harness optimization <../user-guide/recipes/gepa.rst>`__ for a
  worked harness example, or `SAO rollout training
  <../user-guide/recipes/sao.rst>`__ for a GPU training example with results.
- Use the `HTTP API reference <../reference/http-api.rst>`__ when connecting
  your own agent: it covers inference headers, feedback reports, and release
  management.

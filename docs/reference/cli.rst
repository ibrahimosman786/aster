Aster CLI: serve
===============

``aster serve`` reads a deployment config and starts every
process the config declares, in dependency order. (The wheel also installs
``aster-native``, the loop runner the ``native`` adapter launches per
rollout. Nothing calls it by hand.)

.. code:: bash

   export ASTER_TOKEN="$(openssl rand -hex 16)"
   aster serve -c recipes/basic/external-provider.yaml

The config binds every address, so Aster starts only with a token.

``aster serve`` runs in the foreground and holds the terminal until Ctrl-C. Each
service's ``ready`` probe must pass before the next one starts; when they are
all up, Aster blocks, and a watchdog tears the stack down if any process exits
unexpectedly.

Once the stack is running, Ctrl-C requests graceful shutdown. Pressing it
again during shutdown skips the remaining 30-second grace period and proceeds
to forced cleanup of the managed service processes.

.. container:: config

   ``-c, --config``
       optional config file. No file is loaded unless explicitly selected.

   ``--model [PROVIDER/]MODEL``
       the upstream model. An ``ollama/`` or ``openai/`` prefix fills the endpoint and the key; any other spelling is the model ID as is.

   ``--component NAME``
       run one service of the deployment in this process: ``control``, ``inference``, ``samples``, ``training``, ``evaluation`` or ``data``. The process starts no other child. Without it, one process runs all services. See `Run the services in separate processes <../user-guide/operate.rst#run-the-services-in-separate-processes>`__.

   ``--print-config``
       print every resolved setting with its source (file, command line, environment, automatic, default) and exit without downloading models or starting services. Credentials are masked.

   ``--help``
       the command list

   ``-V, --version``
       the installed Aster version. Takes no command: ``aster --version``.

Check artifacts before an upgrade
---------------------------------

.. code-block:: bash

   aster check-artifacts -c path/to/stack.yaml

The command checks that each scenario's commit history resolves to stored
files. It prints each problem, and it exits with status 1 when it finds one and
0 when it finds none. See the `upgrade steps
<../user-guide/operate.rst#upgrade-from-an-aster-that-wrote-older-formats>`__.

Selecting the model
-------------------

Select a file with ``-c``. Without it, Aster uses CLI inference settings and
does not load a config file on its own. Configuration values use
their full public namespaces as shown above.

The optional ``--model`` shorthand remains supported: ``ollama/`` fills
``http://127.0.0.1:11434`` and a placeholder key; ``openai/`` fills
``https://api.openai.com`` and reads ``ASTER_UPSTREAM_API_KEY``. Other prefixes
and bare values are model IDs and need an upstream URL.
An explicit ``--inference.upstream-url`` or ``--inference.upstream-api-key`` override wins over
the prefix.

.. code:: bash

   aster serve --model ollama/gemma4:26b

Aster bundles no deployment profiles. ``aster serve --recipe <name>`` exits
with ``--recipe <name>: built in profiles were removed; pass -c <config file>``.
Pass a recipe's deployment config with ``-c`` instead.

Overriding config values
------------------------

Canonical CLI paths match the sections of a configuration file. Declared fields use the
same type parser for both inputs; explicit CLI values override YAML. Opaque
component objects support leaf overrides, validated by their owning component.

.. code:: bash

   aster serve -c path/to/training.yaml \
     --inference.model-path ~/models/Qwen2.5-1.5B-Instruct \
     --training.config.checkpoint_dir /tmp/ckpt

Use public namespaces to move a stack's state without editing its config.
Bare and ``aster.*`` aliases remain accepted:

.. code:: bash

   aster serve -c recipes/basic/external-provider.yaml \
     --storage.agent-record-dir .aster/agent-record \
     --storage.artifact-work-dir .aster/artifact-work \
     --storage.artifact-cache-dir .aster/artifact-cache

Running one service
-------------------

``--component`` starts one service of the deployment instead of the stack. All
processes of a deployment take the same config, so they find the same shared
store:

.. code:: bash

   aster serve -c deploy.yaml --component control --aster.port 8901
   aster serve -c deploy.yaml --component inference --aster.port 8902
   aster serve -c deploy.yaml --component samples --aster.port 8903

A service that only takes work from a queue (``samples``, ``training`` and
``evaluation``) answers ``/healthz`` and nothing else. The ``data`` service
answers the data routes and the scenario reads.

Where it writes
---------------

Each service gets a log and a PID file under ``aster.run-dir``, which defaults
to ``.aster/run``. Aster writes its own state, including records, commit histories,
and the Git-backed snapshot chain, to the ``storage.*`` paths in the config.

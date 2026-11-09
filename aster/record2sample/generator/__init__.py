"""The generator service: a served model writes Harbor tasks, and Aster checks them and runs their rollouts.

The generated-task recipe (``aster.recipe.generated_tasks``) and the deployment's task generator
(:class:`aster.recipe.generated_tasks.TaskGenerator`) run inside the Aster service, where nothing may block the trainer
and nothing should need Docker. The slow, container bound steps therefore run in the generator service, a
process ``aster serve`` starts beside the HTTP service when a deployment carries a ``generator`` section,
and the recipe and the generator drive it over HTTP:

- ``designer``: the task contract as a prompt, the served model asked for one task through Aster (every
  proposal an inference record with a receipt), the reply parsed into the instruction, the files and a hint.
- ``harbor``: the reply held to the authoring rules, the task written with ``aster.core.tasks``, tasks
  deduplicated by content, Harbor's oracle and nop agents run through the ``harbor`` command line, a split
  per generation.
- ``terminus``: Terminus 2 for the generator's rollouts, whose rollout is still verified when the agent fills its
  context or a send-keys to its terminal fails (selected by ``import_path``; the only module here that imports
  harbor).
- ``inputs``: ``TaskGenerationRequest``, what a task generator is asked for, and the materials the designer
  reads.
- ``service``: the HTTP API and its job runner; ``client``: the same steps as asynchronous calls; ``wire``:
  the JSON forms. The ``generator`` section that starts the service is parsed in
  ``aster.service.deploy.generator``, and ``aster.service.deploy.generator_process`` runs the process.

What is method policy, the prompt's experience section, the measurement arms a task asks for and the score a
proposal earns, stays with the method's task generator (``recipes/beta/spade`` is the first).
"""

from aster.record2sample.generator.client import (
    DuplicateTask,
    Generator,
    GeneratorError,
    HttpGenerator,
    ProposedTask,
    TaskNameConflict,
    WrittenTask,
)
from aster.record2sample.generator.designer import (
    Designer,
    DesignerAnswer,
    DesignerError,
    DesignerReplyError,
    DesignerRequest,
    HarborReply,
    AsterDesigner,
    designer_messages,
    designer_prompt,
    parse_harbor_reply,
)
from aster.record2sample.generator.harbor import (
    GeneratedHarborTask,
    HarborRuns,
    OracleResult,
    OracleUnavailable,
    content_hash,
    harbor_task,
    oracle_check,
    reply_errors,
)
from aster.record2sample.generator.inputs import TaskGenerationRequest
from aster.record2sample.generator.service import (
    GeneratorRollouts,
    GeneratorService,
    HarborChecks,
    JobRunner,
    ReadinessProbe,
    AsterGeneratorRollouts,
    TaskChecks,
    readiness_probes,
)

__all__ = [
    "Designer",
    "DesignerAnswer",
    "DesignerError",
    "DesignerReplyError",
    "DesignerRequest",
    "DuplicateTask",
    "GeneratedHarborTask",
    "Generator",
    "GeneratorError",
    "GeneratorRollouts",
    "GeneratorService",
    "HarborChecks",
    "HarborReply",
    "HarborRuns",
    "HttpGenerator",
    "JobRunner",
    "OracleResult",
    "OracleUnavailable",
    "ProposedTask",
    "ReadinessProbe",
    "AsterDesigner",
    "AsterGeneratorRollouts",
    "TaskChecks",
    "TaskGenerationRequest",
    "TaskNameConflict",
    "WrittenTask",
    "content_hash",
    "designer_messages",
    "designer_prompt",
    "harbor_task",
    "oracle_check",
    "parse_harbor_reply",
    "readiness_probes",
    "reply_errors",
]

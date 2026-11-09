"""Where a terminus task may run.

One extension can define an Agent subclass of Harbor's Terminus2, which runs
as Python in the outer runner. Execution requires Aster's sandbox around the
runner and a remote Harbor environment for the terminal task
(``REMOTE_TASK_ENVIRONMENTS``): the task container alone does not isolate
evolved Python in the outer runner.
"""

from __future__ import annotations

from collections.abc import Mapping

from aster_terminus.tree import ENVIRONMENT_ENV, TerminusTreeError, extension_source

from aster.execution.sandbox.process import ProgramExecutor, ProgramLaunchError, SandboxExecutor
from aster.execution.sandbox.remote import REMOTE_TASK_ENVIRONMENTS
from aster.harness.adapters.descriptor import ExecutionValidator


class TerminusExecutionValidator(ExecutionValidator):
    def __call__(self, files: Mapping[str, str], executor: ProgramExecutor) -> None:
        """Refuse unisolated Python and local Docker nested in Aster's jail."""
        try:
            extension = extension_source(files)
        except TerminusTreeError as exc:
            raise ProgramLaunchError(str(exc)) from exc
        remote = " or ".join(sorted(REMOTE_TASK_ENVIRONMENTS))
        if isinstance(executor, SandboxExecutor):
            environment = executor.env.get(ENVIRONMENT_ENV, "")
            credentials = REMOTE_TASK_ENVIRONMENTS.get(environment)
            if credentials is None:
                raise ProgramLaunchError(
                    "terminus Docker cannot run under evolution.executor: sandbox; set ASTER_TERMINUS_ENVIRONMENT to "
                    f"a remote task environment ({remote}) and include it in evolution.sandbox.env_from"
                )
            if not executor.egress_hosts or not all(executor.env.get(name) for name in credentials):
                raise ProgramLaunchError(
                    f"sandboxed terminus on {environment} requires egress_hosts and "
                    f"{', '.join(credentials)} in sandbox.env_from"
                )
        elif extension is not None:
            raise ProgramLaunchError(
                f"terminus extension requires evolution.executor: sandbox with remote tasks ({remote})"
            )

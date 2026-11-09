"""``aster serve`` — start managed inference, connect a provider, or run a configured stack.

A configuration file and CLI-only input describe components, not process definitions.
Aster assembles inference, training and HTTP processes, and the generator service of a
``generator`` section. Other method services are independently deployed; recipes consume
their endpoints. All processes share the executor lifecycle, readiness and cleanup
machinery. HTTP assembly lives in :mod:`aster.service.assembly`.

Module responsibilities:
    config_utils: YAML loading, environment interpolation and recipe source paths.
    service_config: Typed shared settings consumed by HTTP app assembly.
    deployment_config: Selected component schemas, public layout and validation.
    cli: CLI help, dotted override syntax and precedence.
    inference / training: Component-specific process and runtime assembly.
    generator: The generator service child a ``generator`` section adds before the HTTP service.
    execution: Process definition validation and executor selection.
    diagnostics: Resolved settings and their sources for the startup log.
    process / guard: Worker process lifecycle and remote-owner cleanup.
    orchestrator: Launch coordination, supervision and HTTP child entrypoint.

Shared type conversion lives in ``aster.core.config``; native argument encoding
lives in ``aster.execution.executor.arguments``. Import those owners directly.
"""

from aster.artifact.git_lfs import GitLFSRepositoryBackend
from aster.service.deploy.cli import build_parser
from aster.service.deploy.config_utils import PROJECT_ROOT, DeployConfigError, load_config
from aster.service.deploy.orchestrator import DeployStartupError, main, run_service
from aster.service.deploy.service_config import ServiceConfig, service_config_from_mapping


def build_app(settings, **kwargs):
    from aster.service.assembly import build_app as _build_app

    return _build_app(settings, **kwargs)


def build_dispatcher(settings, **kwargs):
    from aster.service.assembly import build_dispatcher as _build_dispatcher

    return _build_dispatcher(settings, **kwargs)


__all__ = [
    "PROJECT_ROOT",
    "DeployConfigError",
    "DeployStartupError",
    "GitLFSRepositoryBackend",
    "ServiceConfig",
    "build_app",
    "build_dispatcher",
    "build_parser",
    "load_config",
    "main",
    "run_service",
    "service_config_from_mapping",
]

"""The harness layer: a harness as a file tree, rendered for one agent, run, and read back.

The map, one subpackage per job:

``tree/``
    what a harness is: ``HarnessTree`` and ``TreePatch``, the checks of its
    files (``checks``, ``validate``), and how a tree renders for one adapter
    (``render``).
``adapters/``
    one directory per agent, the mapping only: an ``adapter.yaml`` (schema in
    ``descriptor``) that says what Aster may evolve and where the agent reads
    each file (kinds in ``parts``), where the agent keeps its directories,
    how it binds a model, and how it runs; and a ``render.py`` with its own
    render steps. pi, opencode, claude, codex, dsh, hermes, and native, the
    program Aster ships. Another distribution adds an adapter through the
    ``aster.harness_adapters`` entry point group.
``tasks/``
    one headless run and its reading: launch on a rendered root through any
    ``aster.execution.sandbox`` executor (``run``), the adapter as the program that
    executor runs and its install (``vendor_install``), the model binding,
    and the trajectory readers.
``harbor/``
    Harbor, seen from a harness: one adapter's agent playing a Harbor task in
    the task's container (``agent``), and rollouts of Harbor tasks with any
    Harbor agent (``rollouts``).
``runners/``
    the program an adapter's ``binary`` points at when Aster ships it:
    ``native`` (the loop, its graph and the resident ``serve`` form).
``capture``
    the capture proxy between a harness and Aster: tags and receipts.
``gateway``
    the loopback gateway an agent process reaches its model and its tools
    through, which meters each call.
``delivery``
    the file tree that serves a snapshot to a client: its source tree rendered
    for the scenario's adapter.

This package depends on core values, runtime and artifact contracts, and
sandbox execution, never on training, recipes, scenario coordination, or the
HTTP service. The evolution loop is ``aster.train.harness_backend``; versioning
(staging, publishing, the commit history, recovery and activation) is Aster's
artifact stack (``aster.artifact``, ``aster.scenario``).
"""

from aster.harness.adapters.descriptor import AdapterDescriptor, ConfigTarget, DescriptorError, load_descriptor
from aster.harness.tasks.run import TaskResult, TaskRunError, TrajectoryKeepError, run_task
from aster.harness.tasks.trajectory import TrajectoryError, read_opencode_session, read_pi_session
from aster.harness.tree import HarnessTree, RenderError, TreePatch, render_tree, validate_tree

__all__ = [
    "AdapterDescriptor",
    "ConfigTarget",
    "DescriptorError",
    "HarnessTree",
    "RenderError",
    "TaskResult",
    "TaskRunError",
    "TrajectoryError",
    "TrajectoryKeepError",
    "TreePatch",
    "load_descriptor",
    "read_opencode_session",
    "read_pi_session",
    "render_tree",
    "run_task",
    "validate_tree",
]

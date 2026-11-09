from __future__ import annotations

import ast
import importlib
import inspect
import subprocess
import sys
from graphlib import CycleError, TopologicalSorter
from itertools import pairwise
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _assert_isolated_import(code: str) -> None:
    subprocess.run(
        [sys.executable, "-c", code],
        check=True,
        text=True,
        capture_output=True,
    )


def _imported_modules(tree: ast.AST, *, package: str = "", module_scope_only: bool = False) -> list[str]:
    """Absolute module targets of every import statement in *tree*.

    A full AST walk over Import/ImportFrom nodes: a module path in a comment
    or docstring cannot false-fail, and an aliased import cannot slip.
    ``from pkg import name`` contributes ``pkg.name`` so submodule imports
    (``from aster.train import slime``) are caught too. Relative imports are
    resolved against *package* (the dotted package containing the module).

    With ``module_scope_only`` imports inside function bodies are excluded —
    that is the lazy-import escape hatch the layering rules allow. Class
    bodies and conditional blocks still execute at import time and count.
    """
    targets: list[str] = []

    def visit(node: ast.AST) -> None:
        for child in ast.iter_child_nodes(node):
            if module_scope_only and isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda):
                continue
            if isinstance(child, ast.Import):
                targets.extend(alias.name for alias in child.names)
            elif isinstance(child, ast.ImportFrom):
                if child.level:
                    parts = package.split(".")
                    base = ".".join(parts[: len(parts) - child.level + 1])
                    module = f"{base}.{child.module}" if child.module else base
                else:
                    module = child.module or ""
                targets.extend(f"{module}.{alias.name}" for alias in child.names)
            visit(child)

    visit(tree)
    return targets


def _imports_of(targets: list[str], forbidden_prefix: str) -> list[str]:
    return [target for target in targets if target == forbidden_prefix or target.startswith(forbidden_prefix + ".")]


METHOD_PACKAGES = ("harness_evolve", "openclawrl", "sao", "tttd")


def test_semantic_router_runtime_revision_matches_submodule_pin() -> None:
    from aster.service.deploy.routing.containers import SEMANTIC_ROUTER_REVISION

    # Read the gitlink without requiring the submodule to be initialized. Wheels use the packaged constant.
    entry = subprocess.check_output(
        ["git", "ls-files", "--stage", "--", "third_party/semantic-router"],
        cwd=REPO_ROOT,
        text=True,
        timeout=10,
    )
    assert entry.split() == ["160000", SEMANTIC_ROUTER_REVISION, "0", "third_party/semantic-router"]


def test_infra_never_imports_a_method_package() -> None:
    # The whole of aster is the machinery the method packages build on,
    # never the reverse. Dotted recipe references import cookbook code only
    # when the operator selects it, so no aster module has any reason to name a
    # method at module scope or inside a function.
    offenders: list[str] = []
    for path in sorted((REPO_ROOT / "aster").rglob("*.py")):
        package = ".".join(path.parent.relative_to(REPO_ROOT).parts)
        imported = _imported_modules(ast.parse(path.read_text(encoding="utf-8")), package=package)
        offenders.extend(f"{path.relative_to(REPO_ROOT)} -> {target}" for target in _imports_of(imported, "recipes"))
    assert offenders == []


def test_scenario_domain_does_not_depend_on_recipes() -> None:
    module = importlib.import_module("aster.scenario.scenario")
    tree = ast.parse(inspect.getsource(module))

    imported = _imported_modules(tree, package="aster.scenario")
    for method in METHOD_PACKAGES:
        assert _imports_of(imported, f"aster.{method}") == []


def test_core_package_does_not_depend_on_artifacts() -> None:
    # The pure identity types (SnapshotRef and friends) live in aster.core;
    # aster.artifact builds on them, never the other way around.

    for name in (
        "aster.core",
        "aster.core.records_types",
        "aster.core.snapshot",
        "aster.core.errors",
    ):
        module = importlib.import_module(name)
        tree = ast.parse(inspect.getsource(module))
        imported = _imported_modules(tree, package="aster.core")
        assert _imports_of(imported, "aster.artifact") == [], name


def test_harbor_task_values_and_validation_do_not_depend_on_harness() -> None:
    for module_name in ("aster.core.tasks.harbor", "aster.record2sample.generator.harbor"):
        module = importlib.import_module(module_name)
        imported = _imported_modules(ast.parse(inspect.getsource(module)), package=module_name.rpartition(".")[0])
        assert _imports_of(imported, "aster.harness") == [], module_name


def test_release_id_chain_does_not_depend_on_scenario_or_trainer() -> None:
    module = importlib.import_module("aster.artifact.snapshot_chain")
    tree = ast.parse(inspect.getsource(module))

    imported = _imported_modules(tree, package="aster.artifact")
    assert _imports_of(imported, "aster.scenario") == []
    assert _imports_of(imported, "aster.train") == []


def test_record_contracts_and_retention_policy_do_not_import_database_adapters() -> None:
    module = importlib.import_module("aster.storage.records")
    tree = ast.parse(inspect.getsource(module))

    imported = _imported_modules(tree, package="aster.storage")
    for dependency in (
        "aster.scenario",
        "aster.train",
        "aster.storage",
        "aster.artifact",
        "sqlite3",
        "sqlalchemy",
        "alembic",
    ):
        assert _imports_of(imported, dependency) == []


def test_importing_record_contracts_does_not_load_database_adapters() -> None:
    _assert_isolated_import(
        "import sys; from aster.storage.records import RecordStore; "
        "from aster.storage.scenario import ScenarioStorage, ScenarioStore; "
        "assert not [name for name in sys.modules if name.startswith("
        "('sqlalchemy', 'psycopg', 'sqlite3', 'aster.storage.sqlite', "
        "'aster.storage.postgres', 'aster.storage.sql_records'))]; "
        "from aster.storage.sqlite import SQLiteScenarioStorage; "
        "from aster.storage.postgres import PostgresScenarioStorage; "
        "assert issubclass(SQLiteScenarioStorage, ScenarioStorage); "
        "assert issubclass(PostgresScenarioStorage, ScenarioStorage)"
    )


def test_sql_record_implementations_do_not_depend_on_scenario_or_training() -> None:
    for module_name in ("aster.storage.sql_records", "aster.storage.sqlite"):
        module = importlib.import_module(module_name)
        tree = ast.parse(inspect.getsource(module))

        imported = _imported_modules(tree, package="aster.storage")
        assert _imports_of(imported, "aster.scenario") == [], module_name
        assert _imports_of(imported, "aster.train") == [], module_name


def test_shared_sql_record_operations_do_not_select_sqlite() -> None:
    module = importlib.import_module("aster.storage.sql_records")
    imported = _imported_modules(ast.parse(inspect.getsource(module)), package="aster.storage")
    for dependency in ("aster.storage.sqlite", "sqlite3", "sqlalchemy.dialects.sqlite"):
        assert _imports_of(imported, dependency) == []


def test_dispatcher_does_not_select_a_record_backend() -> None:
    module = importlib.import_module("aster.dispatcher")
    imported = [
        target
        for path in sorted((REPO_ROOT / "aster/dispatcher").rglob("*.py"))
        for target in _imported_modules(ast.parse(path.read_text(encoding="utf-8")), package="aster.dispatcher")
    ]
    assert all(
        any(
            target == contract or target.startswith(contract + ".")
            for contract in (
                "aster.storage.artifact_items",
                "aster.storage.control_lease",
                "aster.storage.coordination",
                "aster.storage.data",
                "aster.storage.data_queue",
                "aster.storage.data_sync",
                "aster.storage.job_data",
                "aster.storage.record_items",
                "aster.storage.records",
                "aster.storage.samples",
                "aster.storage.served_models",
                "aster.storage.scenario",
                "aster.storage.tasks",
                "aster.storage.work_queue",
            )
        )
        for target in _imports_of(imported, "aster.storage")
    )
    for dependency in ("sqlite3", "sqlalchemy", "psycopg"):
        assert _imports_of(imported, dependency) == []

    for constructor in (module.Dispatcher, module.build_default_dispatcher):
        parameter = inspect.signature(constructor).parameters["scenario_storage"]
        assert parameter.default is inspect.Parameter.empty


def test_http_app_requires_dispatcher_without_selecting_storage() -> None:
    module = importlib.import_module("aster.service.app")
    imported = _imported_modules(ast.parse(inspect.getsource(module)), package="aster.service")
    assert all(
        target == "aster.storage.records" or target.startswith("aster.storage.records.")
        for target in _imports_of(imported, "aster.storage")
    )
    assert _imports_of(imported, "aster.dispatcher.build_default_dispatcher") == []
    assert _imports_of(imported, "aster.service.assembly") == []
    assert inspect.signature(module.create_app).parameters["dispatcher"].default is inspect.Parameter.empty


def test_scenario_storage_contract_and_state_have_only_domain_dependencies() -> None:
    allowed_domains = {
        "aster.storage.commits": ("aster.core",),
        "aster.storage.tasks": ("aster.core",),
        "aster.storage.segments": ("aster.core",),
        "aster.storage.samples": ("aster.core", "aster.storage.data", "aster.storage.tasks"),
        "aster.storage.item_kinds": ("aster.core", "aster.storage.tasks"),
        "aster.storage.job_data": ("aster.core", "aster.storage.segments"),
        "aster.storage.data": (
            "aster.core",
            "aster.storage.item_kinds",
            "aster.storage.job_data",
            "aster.storage.segments",
            "aster.storage.tasks",
        ),
        "aster.storage.evaluations": ("aster.core",),
        "aster.storage.scenario": (
            "aster.core",
            "aster.storage.data",
            "aster.storage.records",
            "aster.storage.commits",
            "aster.storage.tasks",
            "aster.storage.samples",
            "aster.storage.evaluations",
        ),
    }
    for module_name, allowed in allowed_domains.items():
        module = importlib.import_module(module_name)
        tree = ast.parse(inspect.getsource(module))
        imported = _imported_modules(tree, package=module_name.rpartition(".")[0])
        for dependency in imported:
            assert dependency.partition(".")[0] in sys.stdlib_module_names or any(
                dependency == domain or dependency.startswith(domain + ".") for domain in allowed
            ), f"{module_name} imports {dependency}"


def test_scenario_state_enters_only_through_injected_storage() -> None:
    for path in sorted((REPO_ROOT / "aster/scenario").rglob("*.py")):
        package = ".".join(path.parent.relative_to(REPO_ROOT).parts)
        imported = _imported_modules(ast.parse(path.read_text(encoding="utf-8")), package=package)
        # Scenario state and served routes enter through injected storage readers.
        storage_imports = set(_imports_of(imported, "aster.storage")) - set(
            _imports_of(imported, "aster.storage.records")
            + _imports_of(imported, "aster.storage.scenario")
            + _imports_of(imported, "aster.storage.commits")
            + ["aster.storage.served_models.ServedModels"]
        )
        assert storage_imports == set(), str(path.relative_to(REPO_ROOT))
        for dependency in ("sqlite3", "sqlalchemy", "alembic"):
            assert _imports_of(imported, dependency) == [], str(path.relative_to(REPO_ROOT))


def test_backend_agnostic_core_never_imports_slime_backend_at_module_scope() -> None:
    # The most-repeated layering rule: Aster's backend-agnostic core talks to
    # training through the abstract aster.train surface (types, trainer,
    # processors) and to the concrete runtime only through the runtime
    # registry / named Ray actors — it never imports aster.train.slime or
    # aster.train.slime_backend at module scope. A lazy import inside a
    # function (an adapter reaching for the backend it was configured with)
    # is the allowed escape hatch.
    core_packages = (
        "aster/core",
        "aster/dispatcher",
        "aster/service",
        "aster/scenario",
        "aster/storage",
        "aster/artifact",
        "aster/recipe",
        "aster/execution",
    )
    files = [path for package in core_packages for path in sorted((REPO_ROOT / package).rglob("*.py"))]
    # A method package's public half too; its ``slime`` subpackage is the
    # backend half, imported by the training driver and workers only.
    files += [
        path
        for method in METHOD_PACKAGES
        for path in sorted((REPO_ROOT / "recipes" / method).rglob("*.py"))
        if "slime" not in path.relative_to(REPO_ROOT / "recipes" / method).parts[:-1]
    ]
    files += [REPO_ROOT / "aster" / "__init__.py"]
    assert len(files) > 30, "core package sweep looks wrong"

    offenders: list[str] = []
    for path in files:
        package = ".".join(path.parent.relative_to(REPO_ROOT).parts)
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported = _imported_modules(tree, package=package, module_scope_only=True)
        for prefix in ("aster.train.slime", "aster.train.slime_backend"):
            offenders.extend(f"{path.relative_to(REPO_ROOT)}: {target}" for target in _imports_of(imported, prefix))
    assert offenders == []


def test_importing_aster_does_not_load_cookbook_or_slime_packages() -> None:
    _assert_isolated_import(
        "import sys; import aster; from aster.core.version import __version__; "
        "assert aster.__version__ == __version__; "
        "assert not [m for m in sys.modules if m == 'recipes' or m.startswith('recipes.')], "
        "[m for m in sys.modules if m == 'recipes' or m.startswith('recipes.')]; "
        "assert not [m for m in sys.modules if m.startswith('aster.train.slime_backend')], "
        "[m for m in sys.modules if m.startswith('aster.train.slime_backend')]"
    )


def test_scenario_factory_imports_without_a_cycle() -> None:
    # The factory bridges the scenario aggregate and the deployment recipe; a fresh
    # interpreter import in either direction must not deadlock on a cycle.
    _assert_isolated_import("from aster.scenario.factory import ScenarioFactory; assert ScenarioFactory")
    _assert_isolated_import("import aster; from aster.scenario.factory import ScenarioFactory")


def test_checkpoint_storage_import_does_not_require_ray() -> None:
    _assert_isolated_import(
        "import sys; sys.modules['ray'] = None; "
        "from aster.train.slime_backend.aster_adapters import RetentionConfig; "
        "from aster.inference import recovery; "
        "from aster.train.slime_backend.aster_adapters.training_job import storage"
    )


def test_slime_job_preparation_resolves_tttd_torch_lazily() -> None:
    _assert_isolated_import(
        "import sys; sys.modules['torch'] = None; "
        "from aster.train.slime_backend.aster_adapters.preparation import prepare_slime_job; "
        "assert callable(prepare_slime_job)"
    )


def test_harness_training_backend_does_not_require_gpu_dependencies() -> None:
    _assert_isolated_import(
        "import sys; sys.modules['ray'] = None; sys.modules['torch'] = None; "
        "from aster.train.harness_backend.backend import HarnessBackend; "
        "assert HarnessBackend"
    )


def test_slime_training_component_import_does_not_load_megatron_stack() -> None:
    _assert_isolated_import(
        "import sys, types; "
        "ray = types.ModuleType('ray'); "
        "ray.remote = lambda **kwargs: lambda actor: actor; "
        "sys.modules['ray'] = ray; "
        "from aster.train.slime_backend.component import SlimeJobRunner, SlimeTrainingComponent; "
        "assert SlimeJobRunner and SlimeTrainingComponent; "
        "assert not [name for name in sys.modules if name.startswith(('megatron', 'torch', 'slime.ray'))]"
    )


def test_aster_package_dependencies_are_acyclic() -> None:
    # Collapse submodules into their owning top-level Aster package. Walk all
    # imports, including local and relative ones: delaying an import cannot
    # turn a reversed dependency into a valid boundary.
    graph: dict[str, set[str]] = {}
    sources: dict[tuple[str, str], list[str]] = {}
    root = REPO_ROOT / "aster"
    owners = {
        path.stem if path.is_file() else path.name for path in root.iterdir() if path.is_dir() or path.suffix == ".py"
    }
    for path in sorted(root.rglob("*.py")):
        relative = path.relative_to(root)
        owner = relative.parts[0].removesuffix(".py")
        package = ".".join(path.parent.relative_to(REPO_ROOT).parts)
        graph.setdefault(owner, set())
        for target in _imported_modules(ast.parse(path.read_text(encoding="utf-8")), package=package):
            if target == "aster":
                dependency = "__init__"
            elif target.startswith("aster."):
                dependency = target.split(".")[1]
                if dependency not in owners:
                    # Imports from the public facade depend on that facade,
                    # even when the selected name is a class or constant.
                    dependency = "__init__"
            else:
                continue
            if dependency != owner:
                graph[owner].add(dependency)
                sources.setdefault((owner, dependency), []).append(f"{path.relative_to(REPO_ROOT)} -> {target}")
    try:
        tuple(TopologicalSorter(graph).static_order())
    except CycleError as exc:
        cycle = exc.args[1]
        details = [source for left, right in pairwise(cycle) for source in sources.get((right, left), [])]
        raise AssertionError(f"Aster package dependency cycle: {cycle}\n" + "\n".join(details)) from exc


def test_core_storage_and_sandbox_only_depend_on_lower_layers() -> None:
    allowed = {
        "core": ("aster.core",),
        "storage": ("aster.core", "aster.storage"),
        "execution/sandbox": (
            "aster.core",
            "aster.execution.lifecycle",
            "aster.execution.processes",
            "aster.execution.sandbox",
        ),
    }
    for owner, prefixes in allowed.items():
        for path in sorted((REPO_ROOT / "aster" / owner).rglob("*.py")):
            package = ".".join(path.parent.relative_to(REPO_ROOT).parts)
            for target in _imported_modules(ast.parse(path.read_text(encoding="utf-8")), package=package):
                if target == "aster" or target.startswith("aster."):
                    assert any(
                        target == prefix or target.startswith(prefix + ".") for prefix in prefixes
                    ), f"{path.relative_to(REPO_ROOT)} imports {target}"


def test_package_scan_includes_relative_local_and_facade_imports() -> None:
    tree = ast.parse("from ..storage import commits\ndef load():\n    import aster\n    from aster import Scenario\n")
    assert _imported_modules(tree, package="aster.scenario") == ["aster.storage.commits", "aster", "aster.Scenario"]


def test_training_jobs_and_serving_import_require_no_model_framework() -> None:
    _assert_isolated_import(
        "import sys; "
        "sys.modules.update(dict.fromkeys(('ray', 'torch', 'slime', 'sglang', 'megatron'))); "
        "from aster.train.component import TrainingComponent, TrainingJob; "
        "from aster.inference.serving import AdapterServingRuntime, FullWeightServingRuntime; "
        "from aster.train.jobs import JobLoop; "
        "from aster.train.local_jobs import LocalJobComponent"
    )


def test_inference_recovery_requires_no_model_framework() -> None:
    _assert_isolated_import(
        "import sys; "
        "sys.modules.update(dict.fromkeys(('ray', 'torch', 'slime', 'sglang', 'megatron'))); "
        "from aster.inference.recovery import InferenceControl; "
        "from aster.inference.recovery import EngineHealthMonitor"
    )


def test_inference_contracts_import_only_lower_contracts_and_no_backend() -> None:
    # Include imports inside functions: delaying an import does not make a
    # contract depend on an integration or on a module above it.
    allowed = {
        "interfaces.py": (),
        "recovery.py": (),
        "residency.py": ("aster.inference.interfaces",),
        "deployment.py": ("aster.inference.interfaces",),
        "registry.py": ("aster.inference.interfaces",),
        "serving.py": ("aster.inference.interfaces", "aster.inference.residency"),
    }
    for name, prefixes in allowed.items():
        path = REPO_ROOT / "aster/inference" / name
        imported = _imported_modules(ast.parse(path.read_text(encoding="utf-8")), package="aster.inference")
        for dependency in ("aster.train", "slime", "sglang", "vllm", "megatron"):
            assert _imports_of(imported, dependency) == [], name
        for target in _imports_of(imported, "aster.inference"):
            assert any(target == prefix or target.startswith(prefix + ".") for prefix in prefixes), f"{name}: {target}"


def test_training_contracts_and_executors_never_import_model_backends() -> None:
    paths = [REPO_ROOT / "aster/train/component.py", *sorted((REPO_ROOT / "aster/execution/executor").rglob("*.py"))]
    for path in paths:
        package = ".".join(path.parent.relative_to(REPO_ROOT).parts)
        imported = _imported_modules(ast.parse(path.read_text(encoding="utf-8")), package=package)
        for dependency in ("aster.inference", "aster.train", "slime", "sglang", "megatron"):
            assert _imports_of(imported, dependency) == [], str(path.relative_to(REPO_ROOT))


def test_inference_backends_never_import_training_implementations() -> None:
    for path in sorted((REPO_ROOT / "aster/inference").rglob("*.py")):
        package = ".".join(path.parent.relative_to(REPO_ROOT).parts)
        imported = _imported_modules(ast.parse(path.read_text(encoding="utf-8")), package=package)
        for dependency in ("aster.train", "slime", "slime_plugins", "megatron"):
            assert _imports_of(imported, dependency) == [], str(path.relative_to(REPO_ROOT))


def test_inference_and_training_contracts_import_without_loading_backends() -> None:
    _assert_isolated_import(
        "import sys; "
        "sys.modules.update(dict.fromkeys(('ray', 'torch', 'slime', 'sglang', 'megatron', 'aster.inference.sglang'))); "
        "import aster.inference; from aster.inference import registry, serving; from aster.train import component; "
        "assert not [name for name in sys.modules "
        "if name.startswith(('aster.inference.sglang.', 'aster.train.slime_backend'))]"
    )


def test_training_backends_never_import_inference_implementations() -> None:
    for path in sorted((REPO_ROOT / "aster/train").rglob("*.py")):
        package = ".".join(path.parent.relative_to(REPO_ROOT).parts)
        imported = _imported_modules(ast.parse(path.read_text(encoding="utf-8")), package=package)
        assert _imports_of(imported, "aster.inference") == [], str(path.relative_to(REPO_ROOT))


def test_task_generation_contracts_do_not_depend_on_their_consumers() -> None:
    # The generator service owns the request; the generated-task recipe owns the generator contract.
    for module_name, package, consumers in (
        (
            "aster.record2sample.generator.inputs",
            "aster.record2sample.generator",
            ("aster.train", "aster.recipe", "recipes"),
        ),
        ("aster.recipe.generated_tasks.generator", "aster.recipe.generated_tasks", ("aster.train", "recipes")),
    ):
        module = importlib.import_module(module_name)
        imported = _imported_modules(ast.parse(inspect.getsource(module)), package=package)
        for dependency in consumers:
            assert _imports_of(imported, dependency) == [], module_name


def test_execution_package_has_no_legacy_entry_points() -> None:
    for name in ("sandbox", "background_jobs.py", "processes.py"):
        assert not (REPO_ROOT / "aster" / name).exists()
    tree = ast.parse((REPO_ROOT / "aster/execution/__init__.py").read_text(encoding="utf-8"))
    assert _imported_modules(tree, package="aster.execution") == []


def test_execution_jobs_depend_only_on_processes_and_lifecycle() -> None:
    # Keep the shared worker independent of the sandbox subsystem.
    tree = ast.parse((REPO_ROOT / "aster/execution/jobs.py").read_text(encoding="utf-8"))
    targets = _imported_modules(tree, package="aster.execution")
    assert all(
        target.split(".")[0] in sys.stdlib_module_names
        or target.startswith(("aster.execution.processes.", "aster.execution.lifecycle."))
        for target in targets
    )


def test_processes_depend_only_on_the_standard_library_and_lifecycle() -> None:
    tree = ast.parse((REPO_ROOT / "aster/execution/processes.py").read_text(encoding="utf-8"))
    imports = _imported_modules(tree, package="aster.execution")
    assert all(
        target.split(".")[0] in sys.stdlib_module_names or target.startswith("aster.execution.lifecycle.")
        for target in imports
    )
    tree = ast.parse((REPO_ROOT / "aster/execution/lifecycle.py").read_text(encoding="utf-8"))
    imports = _imported_modules(tree, package="aster.execution")
    assert all(target.split(".")[0] in sys.stdlib_module_names for target in imports)


def test_record_to_sample_stage_depends_only_on_contracts_below_training() -> None:
    # The trainer and the recipes import the stage, so it never imports them or the generator service.
    allowed = (
        "aster.core",
        "aster.execution.jobs",
        "aster.pipeline_context",
        "aster.record2sample",
    )
    for path in sorted((REPO_ROOT / "aster" / "record2sample").glob("*.py")):
        for target in _imported_modules(ast.parse(path.read_text(encoding="utf-8")), package="aster.record2sample"):
            if target.startswith("aster.record2sample.generator"):
                raise AssertionError(f"{path.relative_to(REPO_ROOT)} imports the generator service: {target}")
            if target == "aster" or target.startswith("aster."):
                assert any(
                    target == prefix or target.startswith(prefix + ".") for prefix in allowed
                ), f"{path.relative_to(REPO_ROOT)} imports {target}"


def test_task_to_job_stage_depends_only_on_contracts_below_training() -> None:
    # The pipeline and the recipes import the stage, so it never imports them.
    allowed = (
        "aster.core",
        "aster.observability",
        "aster.pipeline_context",
        "aster.record2sample",
        "aster.storage.samples",
        "aster.storage.tasks",
        "aster.sample2job",
    )
    paths = [*sorted((REPO_ROOT / "aster" / "sample2job").rglob("*.py")), REPO_ROOT / "aster" / "pipeline_context.py"]
    for path in paths:
        package = ".".join(path.parent.relative_to(REPO_ROOT).parts)
        for target in _imported_modules(ast.parse(path.read_text(encoding="utf-8")), package=package):
            if target == "aster" or target.startswith("aster."):
                assert any(
                    target == prefix or target.startswith(prefix + ".") for prefix in allowed
                ), f"{path.relative_to(REPO_ROOT)} imports {target}"

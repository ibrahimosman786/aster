from __future__ import annotations

import importlib.util

import pytest

import aster
from aster import sample2job


@pytest.mark.unit
@pytest.mark.parametrize(
    "module",
    [
        "aster.session_index",
        "aster.groups",
        "aster.data_source",
        "aster.consumer",
        "aster.trainer_gateway",
        "aster.resolver",
        "aster.client",
        "aster.run",
    ],
)
def test_lifecycle_modules_are_removed(module: str) -> None:
    assert importlib.util.find_spec(module) is None


@pytest.mark.unit
@pytest.mark.parametrize(
    "symbol",
    [
        "SessionHandle",
        "AttemptHandle",
        "TraceKey",
        "RolloutGroupSpec",
        "SessionIndex",
        "ReefClient",
        "ReefClientError",
    ],
)
def test_lifecycle_symbols_are_not_exported(symbol: str) -> None:
    assert not hasattr(aster, symbol)


@pytest.mark.unit
def test_recipe_symbols_are_removed_in_favor_of_processors_and_trainer() -> None:
    assert not hasattr(aster, "TrainerRecipe")
    assert not hasattr(aster, "TrainerRecipeRuntime")
    assert hasattr(aster, "Trainer")


@pytest.mark.unit
@pytest.mark.parametrize(
    "module",
    [
        "aster.routing",
        "aster.core.records",
        "aster.scenarios.records",
        "aster.trainer.managers",
        "aster.trainer.pipelines",
        "aster.trainer.recipe",
        "aster.trainer.recipes",
        "aster.trainer.algorithms",
        "aster.trainer.processors.noop",
        "aster.trainer",
        "aster.trainer.trainer",
        "aster.trainer.processors",
        "aster.backends",
        "aster.backends.base",
        "aster.backends.harness",
        "aster.agent_record_store",
        # Alternate module spellings stay absent: the entity is AgentRecord and
        # its store is RecordStore, both exported from their canonical modules.
        "aster.core.agent_record",
        "aster.service.routes.agent_record",
    ],
)
def test_old_naming_modules_are_removed(module: str) -> None:
    try:
        spec = importlib.util.find_spec(module)
    except ModuleNotFoundError:
        spec = None
    assert spec is None


@pytest.mark.unit
@pytest.mark.parametrize(
    "symbol",
    [
        "ScenarioRouter",
        "TypedRecord",
        "ScenarioRecordStore",
        "ScenarioRuntime",
        "TrainingDataManager",
        "WeightTrainingRecipe",
        "BackendRecipeLoader",
        "TypedRequestService",
        "DuplicateRecordError",
        "WeightUpdatePipeline",
        "Pipeline",
        # Renamed in the records vocabulary unification.
        "AgentData",
        "AgentDataStore",
        "AgentDataCodec",
        "AgentDataConflict",
        # Inlined into the SQL record store as private methods; never a public class again.
        "RecordCodec",
        # The record tables went with RFC #1219: a scenario's records are record items.
        "SQLiteRecordStore",
        "PostgresRecordStore",
    ],
)
def test_old_naming_symbols_are_not_exported(symbol: str) -> None:
    assert not hasattr(aster, symbol)


@pytest.mark.unit
def test_readme_names_are_exported() -> None:
    assert aster.Dispatcher is not None
    assert aster.AgentRecord is not None
    assert aster.RecordStore is not None
    assert aster.Scenario is not None
    assert aster.TrainingPipeline is not None
    assert aster.Sample2Job is not None
    assert aster.Trainer is not None
    assert aster.Recipe is not None


@pytest.mark.unit
def test_dead_accessors_and_symbols_are_removed() -> None:
    import aster.core
    import aster.core.errors
    from aster.dispatcher import Dispatcher
    from aster.scenario.scenario import Scenario
    from aster.service.request_service import RequestService

    # Removed dead code (no production callers).
    assert not hasattr(aster.core, "ReferenceStatus")
    assert not hasattr(aster.core.errors, "ConfigurationError")
    assert not hasattr(Scenario, "advance_to")
    assert not hasattr(RequestService, "current_files")
    # Test-only accessors migrated to canonical paths.
    assert not hasattr(Dispatcher, "recipes")
    assert not hasattr(Scenario, "checkpoint_strategy")
    assert not hasattr(Scenario, "commit_log")


@pytest.mark.unit
def test_naming_unification_renames_are_complete() -> None:
    """One concept, one name: the renamed-away spellings must stay gone."""
    from aster.recipe.base import WeightTrainingRecipe
    from aster.scenario.scenario import Scenario
    from aster.train.trainer import Trainer

    # The objective id is no longer called "algorithm".
    assert not hasattr(WeightTrainingRecipe, "algorithm")
    assert WeightTrainingRecipe.default_parameters() == {}
    assert not hasattr(Trainer, "algorithm")
    assert not hasattr(Trainer, "objective")
    assert not hasattr(Scenario, "algorithm")
    assert not hasattr(Scenario, "objective")
    # Route registration follows the records vocabulary.
    import aster.service.routes as routes

    assert not hasattr(routes, "register_agent_record_routes")
    assert hasattr(routes, "register_record_routes")


@pytest.mark.unit
def test_the_surface_package_is_removed() -> None:
    """Scenario components live in ``aster.artifact.components``; the runtime loads weights directly."""
    assert importlib.util.find_spec("aster.surface") is None


@pytest.mark.unit
def test_recipe_config_field_declarations_replaced_the_config_spelling_quartet() -> None:
    """One config field, one spelling: the field declaration
    (aster.recipe.config_fields.config_field)
    is the YAML key, env name, and parser; the parallel spellings stay gone."""
    import aster.recipe.config as recipe_config
    from aster.recipe.base import WeightTrainingRecipe

    # The per-recipe key list and the per-recipe field hook are replaced by
    # config_field() metadata.
    assert not hasattr(WeightTrainingRecipe, "data_settings")
    assert not hasattr(WeightTrainingRecipe, "_config_fields")
    # The hand-rolled env/config parser helpers the config field parsers replaced.
    for name in ("env_positive_int", "env_float", "config_float"):
        assert not hasattr(recipe_config, name)


@pytest.mark.unit
def test_online_grpo_objective_and_recipe_are_removed() -> None:
    """Neither the online_grpo training objective nor its recipe class may come back.

    Grouped objectives are cookbook-owned now; the grouped machinery (group
    keys, slots, the ``ReportGrouping.decide`` barrier in the report stage) stays. The
    ``online_rft`` kind that replaced this arm is gone too — a filtered-SFT
    data recipe, with nothing in it addressing drift on a continually updated
    policy."""
    from aster.recipe.registry import recipe_class_for
    from aster.train.slime_backend.objectives import resolve_slime_objective

    with pytest.raises(ValueError, match="unknown Slime objective"):
        resolve_slime_objective("online_grpo")
    assert recipe_class_for("online_grpo") is None
    assert recipe_class_for("online_rft") is None


@pytest.mark.unit
def test_noop_naming_is_removed_in_favor_of_recipe() -> None:
    assert not hasattr(aster, "NoopRecipe")
    assert not hasattr(aster.Dispatcher, "noop")
    assert not hasattr(sample2job, "NoopProcessor")
    assert importlib.util.find_spec("aster.noop") is None


@pytest.mark.unit
def test_pairing_interlock_surface_is_replaced_by_the_engine_spec() -> None:
    """The subclassed processor bases gave way to one pipeline over three recipe stages.

    Recipes write a ``Sample2Job`` for ``TrainingPipeline``; the processor bases
    (``DataProcessor``, ``ReportedFeedbackProcessor``, ``ComputedFeedbackProcessor``)
    and the interlock vocabulary (``PairedCandidate``, the
    ``_collect_candidates``/``_terminal_report_ids`` dual bookkeeping) must
    stay gone.
    """
    from aster.record2sample import assembly
    from aster.train.pipeline import TrainingPipeline

    for name in ("DataProcessor", "ReportedFeedbackProcessor", "ComputedFeedbackProcessor"):
        assert not hasattr(sample2job, name)
        assert not hasattr(aster, name)
    assert importlib.util.find_spec("aster.train.processors") is None
    assert not hasattr(assembly, "PairedCandidate")
    assert not hasattr(assembly, "ReportedFeedbackProcessor")
    for hook in ("_collect_candidates", "_terminal_report_ids", "_terminal_source_ids", "_create_batch"):
        assert not hasattr(TrainingPipeline, hook)

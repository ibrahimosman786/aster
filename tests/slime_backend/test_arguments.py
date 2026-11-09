from __future__ import annotations

import argparse
import re
import sys
from types import SimpleNamespace

import pytest

from aster.train.slime_backend.aster_adapters.arguments import SlimeArguments
from aster.train.slime_backend.aster_adapters.slime_arguments import (
    ASTER_BEFORE_TRAIN_STEP_HOOK_PATH,
    ASTER_MEGATRON_INIT_PATH,
    ASTER_MODEL_PROVIDER_PATH,
    add_aster_slime_arguments,
    configure_aster_loss_args,
    finalize_aster_slime_args,
)


def slime_args(**overrides):
    values = {
        "critic_steps_per_actor": 2,
        "critic_save_interval": 1,
        "save": "/tmp/megatron",
        "use_critic": False,
        "offload_train": False,
        "disable_grad_buffers_cpu_backup": False,
        "disable_param_buffers_cpu_backup": False,
        "megatron_lora_rank": 0,
        "megatron_lora_alpha": None,
        "megatron_lora_dropout": 0.0,
        "megatron_lora_target_modules": None,
        "megatron_to_hf_mode": "raw",
        "only_train_params_name_list": None,
        "freeze_params_name_list": None,
        "custom_megatron_init_path": "custom.initialize",
        "custom_model_provider_path": "custom.model_provider",
        "loss_family": None,
        "score_centering": False,
        "advantage_estimator": "grpo",
    }
    values.update(overrides)
    return SlimeArguments(**values)


@pytest.mark.unit
def test_aster_slime_argument_hook_owns_only_aster_options() -> None:
    parser = add_aster_slime_arguments(argparse.ArgumentParser())

    args = parser.parse_args(["--megatron-to-hf-mode=bridge", "--megatron-lora-rank=4", "--use-critic"])

    assert args.megatron_to_hf_mode == "bridge"
    assert args.megatron_lora_rank == 4
    assert args.use_critic is True
    assert args.aster_executor_backend == "auto"


@pytest.mark.unit
def test_finalize_arguments_chains_user_hooks_and_enables_explicit_critic() -> None:
    args = slime_args(
        disable_grad_buffers_cpu_backup=True,
        disable_param_buffers_cpu_backup=True,
        megatron_to_hf_mode="bridge",
        megatron_lora_rank=8,
        custom_megatron_init_path="custom.initialize",
        custom_model_provider_path="custom.model_provider",
        custom_megatron_before_train_step_hook_path="custom.before_step",
    )

    finalize_aster_slime_args(args, ["--use-critic", "--megatron-lora-rank=8"])

    assert args.use_critic is True
    assert args.offload_train is True
    assert args.disable_grad_buffers_cpu_backup is True
    assert args.disable_param_buffers_cpu_backup is True
    assert args.megatron_lora_alpha == 8
    assert args.custom_megatron_init_path == ASTER_MEGATRON_INIT_PATH
    assert args.aster_chained_megatron_init_path == "custom.initialize"
    assert args.custom_model_provider_path == ASTER_MODEL_PROVIDER_PATH
    assert args.aster_chained_model_provider_path == "custom.model_provider"
    # Every optimizer step passes Aster's learning-rate hook, which runs the user's hook first.
    assert args.custom_megatron_before_train_step_hook_path == ASTER_BEFORE_TRAIN_STEP_HOOK_PATH
    assert args.aster_chained_before_train_step_hook_path == "custom.before_step"


@pytest.mark.unit
def test_finalize_arguments_lets_an_explicit_no_offload_train_stand() -> None:
    # --use-critic offloads the idle model by default; a launch that says
    # --no-offload-train keeps the actor and the critic resident.
    args = slime_args(offload_train=False)

    finalize_aster_slime_args(args, ["--use-critic", "--no-offload-train"])

    assert args.use_critic is True
    assert args.offload_train is False


@pytest.mark.unit
def test_finalize_arguments_rejects_nonpositive_critic_steps() -> None:
    with pytest.raises(ValueError, match="critic-steps-per-actor"):
        finalize_aster_slime_args(slime_args(critic_steps_per_actor=0), [])


@pytest.mark.unit
def test_loss_family_projection_uses_public_slime_primitives() -> None:
    sao = slime_args(loss_family="sao")
    configure_aster_loss_args(sao)
    assert sao.advantage_estimator == "cispo"
    # The configured estimator stays on record for a job of another family.
    assert sao.aster_configured_advantage_estimator == "grpo"
    assert sao.compute_advantages_and_returns is True

    topk = slime_args(loss_family="openclawrl")
    configure_aster_loss_args(topk)
    assert topk.compute_advantages_and_returns is True

    neutral = slime_args(loss_family="sft")
    configure_aster_loss_args(neutral)
    assert not hasattr(neutral, "compute_advantages_and_returns")


def component_args(**overrides):
    values = {
        "compute_advantages_and_returns": False,
        "num_rollout": 1,
        "save_hf": "/tmp/hf/checkpoint-{rollout_id}",
        "save": "/tmp/megatron",
        "debug_train_only": False,
        "debug_rollout_only": False,
        "colocate": False,
        "offload_train": False,
        "offload_rollout": False,
        "release_train": False,
        "megatron_lora_rank": 0,
        "rollout_num_gpus": 0,
        "actor_num_nodes": 1,
        "actor_num_gpus_per_node": 4,
        **overrides,
    }
    return SlimeArguments(**values)


@pytest.mark.unit
@pytest.mark.parametrize(
    "overrides",
    [
        {},
        {"megatron_lora_rank": 32},
        {"offload_train": True},
        # The component's own rollout engines: on GPUs of their own, or on some or all of the training GPUs.
        {"rollout_num_gpus": 2},
        {"colocate": True, "offload_train": True, "offload_rollout": True, "rollout_num_gpus": 4},
        {"colocate": True, "offload_train": True, "offload_rollout": True, "rollout_num_gpus": 2},
    ],
)
def test_slime_args_accept_a_run_the_training_component_can_run(overrides) -> None:
    from aster.train.slime_backend.aster_adapters.preflight import validate_slime_args

    validate_slime_args(component_args(**overrides), None)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("overrides", "refusal"),
    [
        # Aster's LoRA adapters are not wired into Slime's weight transfer to its engines.
        ({"rollout_num_gpus": 2, "megatron_lora_rank": 32}, "remove --megatron-lora-rank"),
        ({"debug_train_only": True}, "--debug-train-only"),
        ({"debug_rollout_only": True}, "--debug-rollout-only"),
        ({"num_rollout": 0}, "positive --num-rollout"),
        ({"save_hf": "/tmp/hf/checkpoint"}, "{rollout_id}"),
        # The workers keep running through a job, so nothing releases and recreates them.
        ({"release_train": True}, "remove --release-train"),
    ],
)
def test_slime_args_refuse_what_the_training_component_cannot_run(overrides, refusal) -> None:
    from aster.train.slime_backend.aster_adapters.preflight import validate_slime_args

    with pytest.raises(ValueError, match=re.escape(refusal)):
        validate_slime_args(component_args(**overrides), None)


@pytest.mark.unit
@pytest.mark.parametrize("interval", [0, -1])
def test_finalize_arguments_rejects_nonpositive_critic_save_interval(interval: int) -> None:
    with pytest.raises(ValueError, match="critic-save-interval"):
        finalize_aster_slime_args(slime_args(critic_save_interval=interval), [])


@pytest.mark.unit
@pytest.mark.parametrize("save", [None, " "])
def test_finalize_arguments_requires_save(save: str | None) -> None:
    # Megatron checks --save-interval only with --save, and the bridge reads --save-interval.
    with pytest.raises(ValueError, match="requires --save"):
        finalize_aster_slime_args(slime_args(save=save), [])


@pytest.mark.unit
@pytest.mark.parametrize("interval", [0, -1])
def test_checkpoint_preflight_preserves_invalid_interval_for_validation(tmp_path, interval: int) -> None:
    from aster.train.slime_backend.aster_adapters.preflight import prepare_checkpoint_storage
    from aster.train.slime_backend.aster_adapters.training_job.storage import RetentionConfig

    args = SlimeArguments(
        save_hf=str(tmp_path / "hf" / "{rollout_id}"),
        save=str(tmp_path / "megatron"),
        use_critic=False,
        hf_checkpoint=None,
        load=None,
        megatron_lora_rank=0,
        critic_save_interval=interval,
    )
    with pytest.raises(ValueError, match="critic_save_interval"):
        prepare_checkpoint_storage(args, RetentionConfig())
    assert not (tmp_path / "megatron").exists()


@pytest.mark.unit
def test_slime_parses_tensor_parallel_arguments_without_the_workers_cuda_variable(monkeypatch) -> None:
    """Megatron's check wants CUDA_DEVICE_MAX_CONNECTIONS=1 in the parsing process: the HTTP service and each driver."""
    from aster.train.slime_backend.aster_adapters import slime_arguments, startup
    from aster.train.slime_backend.aster_adapters.megatron import hf_arguments

    seen: list[str | None] = []

    def parse_args(add_custom_arguments):
        import os

        seen.append(os.environ.get("CUDA_DEVICE_MAX_CONNECTIONS"))
        return argparse.Namespace()

    monkeypatch.delenv("CUDA_DEVICE_MAX_CONNECTIONS", raising=False)
    monkeypatch.setitem(sys.modules, "slime.utils.arguments", SimpleNamespace(parse_args=parse_args))
    monkeypatch.setattr(hf_arguments, "add_hf_architecture_arguments", lambda arguments: list(arguments))
    monkeypatch.setattr(slime_arguments, "finalize_aster_slime_args", lambda args, arguments: None)
    startup.parse_slime_args(["--tensor-model-parallel-size=4"])
    assert seen == ["1"]

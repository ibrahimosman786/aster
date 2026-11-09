"""Aster-specific arguments layered onto the runtime's parser hook."""

from __future__ import annotations

import argparse
import copy
from collections.abc import Sequence

from aster.train.algos.registry import loss_family_refs
from aster.train.slime_backend.algorithm import SlimeAlgorithm
from aster.train.slime_backend.loss_families import LOSS_FAMILIES
from aster.train.slime_backend.aster_adapters.arguments import SlimeArguments
from aster.train.slime_backend.aster_adapters.megatron.lora import validate_megatron_lora_args
from aster.train.slime_backend.aster_adapters.preflight import validate_advantage_computation
from aster.train.slime_backend.score_centering import ScoreCenteringSettings, configure_score_centering

ASTER_MEGATRON_INIT_PATH = "aster.train.slime_backend.aster_adapters.worker_hooks.initialize_megatron_objective"
ASTER_MODEL_PROVIDER_PATH = "aster.train.slime_backend.aster_adapters.megatron.model_provider.provide_actor_model"
ASTER_BEFORE_TRAIN_STEP_HOOK_PATH = "aster.train.slime_backend.aster_adapters.worker_hooks.apply_learning_rate_schedule"


def add_aster_slime_arguments(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    """Register options implemented by Aster rather than the runtime."""
    parser.add_argument(
        "--aster-executor-backend",
        default="auto",
        help="Training worker executor: auto (currently ray), ray, or a Slime-compatible Executor import path.",
    )
    parser.add_argument(
        "--megatron-to-hf-mode",
        choices=["raw", "bridge"],
        default="raw",
        help="Weight-conversion implementation selected by the Aster Slime adapter.",
    )
    parser.add_argument("--megatron-lora-rank", type=int, default=0)
    parser.add_argument("--megatron-lora-alpha", type=int, default=None)
    parser.add_argument("--megatron-lora-dropout", type=float, default=0.0)
    parser.add_argument("--megatron-lora-target-modules", type=str, nargs="+", default=None)
    parser.add_argument(
        "--critic-steps-per-actor",
        type=int,
        default=None,
        help="Critic optimizer steps per actor step; unset means the loss family's own default.",
    )
    parser.add_argument("--critic-save", type=str, default=None)
    parser.add_argument(
        "--critic-init",
        type=str,
        default=None,
        help=(
            "Megatron checkpoint directory the critic starts from when its own save root holds no "
            "checkpoint yet: a value model trained on earlier rollouts instead of a cold value head. "
            "Ignored once the critic has saved, and when the directory holds no checkpoint."
        ),
    )
    parser.add_argument(
        "--critic-save-interval",
        type=int,
        default=1,
        help=(
            "Saved rollouts between critic checkpoints (weights and optimizer). 1 saves the critic with every "
            "rollout; a larger value trades a warmer value head after a restart for cheaper saves."
        ),
    )
    parser.add_argument(
        "--critic-lr",
        type=float,
        default=None,
        help="Learning rate for the critic role; unset inherits --lr.",
    )
    parser.add_argument(
        "--custom-pg-loss-function-path",
        type=str,
        default=None,
        help="Aster per-token policy-gradient loss primitive.",
    )
    parser.add_argument(
        "--use-critic",
        action="store_true",
        default=False,
        help="Enable a critic when the selected Slime advantage estimator does not imply one.",
    )
    defaults = ScoreCenteringSettings()
    parser.add_argument(
        "--score-centering",
        action=argparse.BooleanOptionalAction,
        default=False,
        help=(
            "Add score centering (arXiv:2609.20807) to the loss family's policy-gradient loss. The family must "
            "declare its policy-gradient weight; it trains the task rollouts of the component, which record the "
            "sampler's top-K."
        ),
    )
    # Slime registers --score-centering-top-k (its own score centering's top-K, also 128); the term reads it.
    parser.add_argument(
        "--score-centering-min-tail-mass",
        type=float,
        default=defaults.min_tail_mass,
        help=f"Floor of both tail masses before their ratio is taken. Default {defaults.min_tail_mass}.",
    )
    return parser


def finalize_aster_slime_args(args: SlimeArguments, arguments: Sequence[str]) -> None:
    """Restore Aster derivations and install runtime extension hooks."""
    explicitly_enabled_critic = any(
        argument == "--use-critic" or argument.startswith("--use-critic=") for argument in arguments
    )
    explicitly_resident = "--no-offload-train" in arguments
    save = args.save
    if not isinstance(save, str) or not save.strip():
        # The component saves a Megatron checkpoint in --save after every rollout. Megatron also
        # requires --save-interval with --save, but the component does not read it.
        raise ValueError("the Slime training component requires --save for Megatron recovery checkpoints")
    if explicitly_enabled_critic:
        args.use_critic = True
        # The critic shares the actor's GPUs, so whichever is idle is
        # offloaded between their steps unless the launch says
        # --no-offload-train: a pair small enough to stay resident (a frozen
        # LoRA base twice over) trades that memory for the offload cycle.
        args.offload_train = not explicitly_resident

    if args.critic_save_interval < 1:
        raise ValueError("--critic-save-interval must be positive")
    if args.critic_steps_per_actor is not None and args.critic_steps_per_actor <= 0:
        raise ValueError("--critic-steps-per-actor must be positive")
    if args.megatron_lora_alpha is None and args.megatron_lora_rank:
        args.megatron_lora_alpha = args.megatron_lora_rank
    validate_megatron_lora_args(args)

    previous_init = args.custom_megatron_init_path
    if previous_init != ASTER_MEGATRON_INIT_PATH:
        args.aster_chained_megatron_init_path = previous_init
        args.custom_megatron_init_path = ASTER_MEGATRON_INIT_PATH

    # Every optimizer step passes Slime's before-step hook, which sets the rate
    # of a learning-rate schedule a recipe selected (worker_hooks).
    previous_before_step = args.custom_megatron_before_train_step_hook_path
    if previous_before_step != ASTER_BEFORE_TRAIN_STEP_HOOK_PATH:
        args.aster_chained_before_train_step_hook_path = previous_before_step
        args.custom_megatron_before_train_step_hook_path = ASTER_BEFORE_TRAIN_STEP_HOOK_PATH

    if args.megatron_lora_rank:
        previous_provider = args.custom_model_provider_path
        if previous_provider != ASTER_MODEL_PROVIDER_PATH:
            args.aster_chained_model_provider_path = previous_provider
            args.custom_model_provider_path = ASTER_MODEL_PROVIDER_PATH

    configure_aster_loss_args(args)


def configure_aster_loss_args(args: SlimeArguments) -> None:
    """Project loss-family settings after the driver stamps ``loss_family``.

    Delegates to the family's spec: its declarative wire attributes land on
    ``args`` for the adapter layer to consume, then ``configure_backend_args``
    runs — so this module never names an individual family.
    """
    family = args.loss_family
    if not family:
        return
    spec = LOSS_FAMILIES.resolve(family)
    configured = tuple(args.custom_rollout_data_keys or ())
    args.custom_rollout_data_keys = tuple(dict.fromkeys((*configured, *spec.rollout_data_keys)))
    args.aster_rollout_tensor_dtypes = dict(spec.rollout_tensor_dtypes)
    args.aster_external_batch_keys = tuple(spec.external_batch_keys)
    args.aster_rollout_log_skip_keys = tuple(spec.rollout_log_skip_keys)
    spec.configure_backend_args(args)
    configure_score_centering(args, spec)
    if spec.uses_pg_loss_primitive:
        # Route Slime's numerical CISPO callsite onto the family's registered
        # pg primitive: the worker swaps loss.compute_cispo_loss for the
        # function behind custom_pg_loss_function_path (worker_hooks), so no
        # Slime source patch is needed. The routing value is adapter-owned;
        # families only declare the lane. The configured estimator is kept for
        # a job of another family.
        if args.aster_configured_advantage_estimator is None:
            args.aster_configured_advantage_estimator = args.advantage_estimator
        args.advantage_estimator = "cispo"


def loss_family_job_args(args: SlimeArguments, spec: SlimeAlgorithm) -> SlimeArguments:
    """The workers' arguments for a job of ``spec``, a loss family they did not start with.

    ``args`` are the arguments the workers started with. The family brings
    its loss type, its advantage routing, its wire keys and its default driver
    options; every other option keeps its startup value, and the family is
    validated against it. A family that needs driver options, or configures
    the critic (which starts with the workers), must be the startup family.
    """
    source = f"loss family {spec.loss_family!r} selected for a training job"
    if spec.requires_driver_options:
        raise RuntimeError(
            f"{source} requires driver options, which only the startup family parses; "
            "make its objective the recipe's default objective"
        )
    if (
        type(spec).configure_critic_args is not SlimeAlgorithm.configure_critic_args
        or spec.critic_value_head_zero_init
    ):
        raise RuntimeError(
            f"{source} configures the critic, which starts with the workers; make its objective the recipe's "
            "default objective"
        )
    job_args = copy.copy(args)
    job_args.loss_family_ref = loss_family_refs().get(spec.loss_family)
    job_args.loss_type = spec.loss_type
    if args.aster_configured_advantage_estimator is not None:
        job_args.advantage_estimator = args.aster_configured_advantage_estimator
    # Slime's pre-train advantage pass is the family's: the families that keep
    # it need it, the others would have it overwrite their external signals.
    job_args.compute_advantages_and_returns = spec.allows_slime_advantage_computation
    spec.apply_driver_options(job_args, None)
    configure_aster_loss_args(job_args)
    spec.validate_backend_args(job_args)
    try:
        validate_advantage_computation(job_args, spec)
    except ValueError as exc:
        raise RuntimeError(f"{source}: {exc}") from exc
    return job_args


__all__ = [
    "ASTER_BEFORE_TRAIN_STEP_HOOK_PATH",
    "ASTER_MEGATRON_INIT_PATH",
    "ASTER_MODEL_PROVIDER_PATH",
    "add_aster_slime_arguments",
    "configure_aster_loss_args",
    "finalize_aster_slime_args",
    "loss_family_job_args",
]

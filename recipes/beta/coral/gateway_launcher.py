"""Wire the adapter into a CORAL gateway (optional CORAL dependency).

CORAL's ``GatewayManager.start()`` builds ``CoralGatewayMiddleware`` around
LiteLLM's app and hands the result to uvicorn. This module splices the aster
layer into that middleware's inner ``app`` reference:

    uvicorn -> CoralGatewayMiddleware -> AsterGatewayMiddleware -> LiteLLM

CORAL stamps ``x-coral-agent-id``/``x-coral-session-id`` first, then the
aster layer translates them to aster headers, so the adapter never needs
CORAL's key registry. The outer middleware object is left in place —
``GatewayManager.register_agent`` type-checks it, so replacing it would
break agent registration. Requires only that aster is one of the LiteLLM
upstreams (an ``api_base`` pointing at ``aster serve``).

Two entry points, both duck-typed so this module never imports CORAL:

- :func:`attach_aster_adapter` for a ``GatewayManager`` the caller builds
  and starts itself.
- :func:`attach_aster_adapter_to_agent_manager` for CORAL's ``AgentManager``
  orchestration (``coral start`` semantics), which constructs its gateway
  internally during ``start_all()``. The splice lands right after the
  gateway starts and before any agent spawns, so no traffic is missed.

CORAL's gateway grew a ``header_provider`` hook (its ``GatewayManager``
accepts a request-header callback), but the aster layer also mirrors headers
into the JSON body and captures aster's response receipts into the journal —
both outside a request-header hook's reach — so the splice stays.

Written against CORAL commit 0123dfb; the touched surface is the documented
middleware's ``app`` attribute and the manager's gateway-start step.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from recipes.beta.coral.journal import CallJournal
from recipes.beta.coral.middleware import AsterGatewayMiddleware


def attach_aster_adapter(
    gateway_manager: Any,
    *,
    scenario: str,
    journal_path: Path,
    extra_tags: Mapping[str, str] | None = None,
) -> CallJournal:
    """Arrange for the aster layer to sit under a CORAL gateway.

    Call between ``GatewayManager(...)`` construction and ``start()``: it
    wraps the manager's ``start`` so the aster layer is spliced in right
    after CORAL builds its middleware. Returns the journal for the
    reporter side.
    """
    journal = CallJournal(journal_path)
    original_start = gateway_manager.start

    def start_with_adapter() -> None:
        original_start()
        insert_aster_layer(
            gateway_manager._middleware,
            scenario=scenario,
            journal=journal,
            extra_tags=extra_tags,
        )

    gateway_manager.start = start_with_adapter
    return journal


def attach_aster_adapter_to_agent_manager(
    agent_manager: Any,
    *,
    scenario: str,
    journal_path: Path,
    extra_tags: Mapping[str, str] | None = None,
) -> CallJournal:
    """Arrange for the aster layer to sit under an ``AgentManager``-owned gateway.

    Call between ``AgentManager(...)`` construction and ``start_all()``.
    The manager builds and starts its ``GatewayManager`` inside its
    gateway-start step, before any agent process spawns; this wraps that
    step so the aster layer is spliced in the moment the gateway is up.
    Raises at start time when the config never enabled the gateway —
    silently running unattributed agents is worse than failing.
    """
    journal = CallJournal(journal_path)
    original_start_gateway = agent_manager._start_gateway_if_enabled

    def start_gateway_with_adapter() -> None:
        original_start_gateway()
        gateway = getattr(agent_manager, "_gateway", None)
        if gateway is None:
            raise RuntimeError(
                "the CORAL manager did not start a gateway — the aster adapter needs "
                "agents.gateway.enabled: true in the task config"
            )
        insert_aster_layer(
            gateway._middleware,
            scenario=scenario,
            journal=journal,
            extra_tags=extra_tags,
        )

    agent_manager._start_gateway_if_enabled = start_gateway_with_adapter
    return journal


def insert_aster_layer(
    coral_middleware: Any,
    *,
    scenario: str,
    journal: CallJournal,
    extra_tags: Mapping[str, str] | None = None,
) -> None:
    """Splice :class:`AsterGatewayMiddleware` under an existing CORAL middleware.

    Idempotent: a middleware whose ``app`` is already the aster layer is left
    alone, so a retried launcher does not stack two layers.
    """
    if coral_middleware is None or not hasattr(coral_middleware, "app"):
        raise TypeError("expected a started CoralGatewayMiddleware with an `app` attribute")
    if isinstance(coral_middleware.app, AsterGatewayMiddleware):
        return
    coral_middleware.app = AsterGatewayMiddleware(
        coral_middleware.app,
        scenario=scenario,
        journal=journal,
        extra_tags=extra_tags,
    )

"""End-to-end: adapter -> real aster service -> receipt -> journal -> report.

The aster service is real (``aster.service.app.create_app`` with a stub
inference backend, exactly as aster's own service tests build it); the
middleware forwards to it over real HTTP. What LiteLLM would contribute in
production — an opaque proxy hop — is the pass-through the shim reproduces.

Requires the aster package importable (run from an aster checkout); skipped
otherwise so the adapter's own suite stays standalone.
"""

from __future__ import annotations

import asyncio
import json

import pytest

aster_service = pytest.importorskip("aster.service.app", reason="requires an aster checkout")

from aiohttp.test_utils import TestClient, TestServer
from tests.support.inference import wait_for_inference

from recipes.beta.coral.journal import CallJournal
from recipes.beta.coral.middleware import AsterGatewayMiddleware
from recipes.beta.coral.reporter import AttemptReport
from aster.artifact import InMemoryRepositoryBackend
from aster.dispatcher import Dispatcher
from aster.inference.http import InferenceProxyRuntime
from aster.inference.interfaces import InferenceHandler
from aster.recipe import Recipe
from aster.storage.sql_coordination import memory_coordination
from aster.storage.sqlite import SQLiteScenarioStorage


class _EchoBackend(InferenceHandler):
    async def inference(self, artifact, path, payload):
        del artifact, path, payload
        return {"choices": [{"message": {"content": "a proposed config"}}]}


class _HttpForwarder:
    """ASGI app that forwards to the aster test client — the LiteLLM stand-in."""

    def __init__(self, client: TestClient) -> None:
        self.client = client

    async def __call__(self, scope, receive, send):
        headers = {bytes(k).decode("latin-1"): bytes(v).decode("latin-1") for k, v in scope["headers"]}
        body = bytearray()
        while True:
            message = await receive()
            body.extend(message.get("body", b""))
            if not message.get("more_body"):
                break
        upstream = await self.client.post(scope["path"], data=bytes(body), headers=headers)
        payload = await upstream.read()
        await send(
            {
                "type": "http.response.start",
                "status": upstream.status,
                "headers": [(k.encode(), v.encode()) for k, v in upstream.headers.items()],
            }
        )
        await send({"type": "http.response.body", "body": payload})


def _coral_scope():
    return {
        "type": "http",
        "method": "POST",
        "path": "/v1/chat/completions",
        "headers": [
            (b"content-type", b"application/json"),
            (b"authorization", b"Bearer sk-coral-agent-1-deadbeef"),
            (b"x-coral-agent-id", b"agent-1"),
            (b"x-coral-session-id", b"commit-a"),
        ],
    }


async def _post_through(mw, scope, body: bytes):
    sent = []

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(message):
        sent.append(message)

    await mw(scope, receive, send)
    status = next(m["status"] for m in sent if m["type"] == "http.response.start")
    payload = b"".join(m.get("body", b"") for m in sent if m["type"] == "http.response.body")
    return status, payload


@pytest.mark.unit
def test_full_loop_against_real_aster_service(tmp_path):
    # The runtime's engine has an HTTP address, so the scenario has a served model; the stub answers for it.
    dispatcher = Dispatcher(
        Recipe(runtime=InferenceProxyRuntime(base_url="http://engine.test", model_path="aster")),
        InMemoryRepositoryBackend.factory(directory=tmp_path / "repository"),
        scenario_storage=SQLiteScenarioStorage(),
        coordination=memory_coordination(),
    )
    # An inference call never creates a scenario.
    dispatcher.get_or_create_scenario("coral-demo")

    async def run():
        reef_client = TestClient(TestServer(aster_service.create_app(dispatcher, inference_handler=_EchoBackend())))
        await reef_client.start_server()
        try:
            await wait_for_inference(reef_client, "coral-demo")
            journal = CallJournal(tmp_path / "calls.jsonl")
            mw = AsterGatewayMiddleware(
                _HttpForwarder(reef_client),
                scenario="coral-demo",
                journal=journal,
                extra_tags={"coral-run": "run-1"},
            )

            # inference through the adapter: aster must accept (scenario header
            # stamped by us, not by CORAL) and hand back a receipt
            status, payload = await _post_through(
                mw, _coral_scope(), json.dumps({"messages": [{"role": "user", "content": "hi"}]}).encode()
            )
            assert status == 200
            assert json.loads(payload)["choices"][0]["message"]["content"] == "a proposed config"

            (record,) = journal.records()
            assert record.agent_record_id, "aster receipt must be captured"
            assert record.agent_id == "agent-1"

            # grader finalizes later: report with exact references
            report = AttemptReport(
                scenario="coral-demo",
                agent_id="agent-1",
                commit_hash="commit-a",
                score=0.9,
                status="improved",
                run_id="run-1",
                references=tuple(journal.record_ids_since(0, "agent-1", "commit-a")),
            )
            assert report.references == (record.agent_record_id,)

            first = await reef_client.post(
                "/aster/report", json=report.payload(), headers={"x-aster-scenario": "coral-demo"}
            )
            assert first.status == 200
            echoed = (await first.json())["agent_record_id"]

            # duplicate grader run: identical resend dedups, no double count
            retry = await reef_client.post(
                "/aster/report", json=report.payload(), headers={"x-aster-scenario": "coral-demo"}
            )
            assert retry.status == 200
            assert (await retry.json())["agent_record_id"] == echoed

            # conflicting resend (same id, different score) must be rejected
            conflicting = dict(report.payload())
            conflicting["score"] = 0.1
            conflict = await reef_client.post(
                "/aster/report", json=conflicting, headers={"x-aster-scenario": "coral-demo"}
            )
            assert conflict.status == 409
        finally:
            await reef_client.close()

    try:
        asyncio.run(run())
    finally:
        dispatcher.close()

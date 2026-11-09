from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from aiohttp.test_utils import TestClient, TestServer
from tests.support.inference import wait_for_inference

from aster.artifact import GitLFSRepositoryBackend, InMemoryRepositoryBackend
from aster.core import RequestType
from aster.dispatcher import Dispatcher, build_default_dispatcher
from aster.inference.http import InferenceProxyRuntime
from aster.inference.interfaces import InferenceHandler
from aster.recipe import Recipe
from aster.service.app import RequestService, create_app
from aster.storage.sql_coordination import memory_coordination
from aster.storage.sqlite import SQLiteScenarioStorage


class StubInferenceHandler(InferenceHandler):
    async def inference(self, artifact, path, payload):
        del artifact, path, payload
        return {"ok": True}


@pytest.mark.unit
@pytest.mark.parametrize(
    "registered, headers",
    [
        (False, {}),
        # A deployment serves one recipe, so requests cannot choose one: a stray
        # ``x-aster-recipe`` is an ordinary unknown header and changes nothing.
        (False, {"x-aster-recipe": "different"}),
        # A registered scenario keeps its binding.
        (True, {}),
    ],
    ids=["new", "stray-recipe-header", "registered"],
)
def test_a_report_creates_or_reuses_the_scenario(registered: bool, headers: dict) -> None:
    async def run() -> None:
        dispatcher = build_default_dispatcher(
            scenario_storage=SQLiteScenarioStorage(), coordination=memory_coordination()
        )
        if registered:
            RequestService(dispatcher).accept(
                {"x-aster-scenario": "scenario"}, {"score": 1.0}, request_type=RequestType.REPORT
            )
        client = TestClient(TestServer(create_app(dispatcher)))
        await client.start_server()
        try:
            response = await client.post(
                "/aster/report", headers={"x-aster-scenario": "scenario", **headers}, json={"score": 1.0}
            )

            assert response.status == 200
            assert dispatcher.registry.get_optional("scenario") is not None
        finally:
            await client.close()

    asyncio.run(run())


@pytest.mark.unit
@pytest.mark.parametrize("headers", [{}, {"x-aster-recipe": "different"}], ids=["plain", "stray-recipe-header"])
def test_inference_answers_a_created_scenario_and_never_creates_one(tmp_path, headers: dict) -> None:
    async def run() -> None:
        dispatcher = Dispatcher(
            Recipe(runtime=InferenceProxyRuntime(base_url="http://engine.test", model_path="aster")),
            InMemoryRepositoryBackend.factory(directory=tmp_path / "repository"),
            scenario_storage=SQLiteScenarioStorage(),
            coordination=memory_coordination(),
        )
        client = TestClient(TestServer(create_app(dispatcher, inference_handler=StubInferenceHandler())))
        await client.start_server()
        payload = {"model": "aster", "messages": []}
        try:
            unknown = await client.post(
                "/v1/chat/completions", headers={"x-aster-scenario": "scenario", **headers}, json=payload
            )
            assert unknown.status == 404
            assert dispatcher.registry.get_optional("scenario") is None

            dispatcher.get_or_create_scenario("scenario")
            await wait_for_inference(client, "scenario")
            response = await client.post(
                "/v1/chat/completions", headers={"x-aster-scenario": "scenario", **headers}, json=payload
            )
            assert response.status == 200, await response.text()
            assert await response.json() == {"ok": True}
        finally:
            await client.close()
            dispatcher.close()

    asyncio.run(run())


@pytest.mark.integration
def test_request_recovers_durable_scenario_without_resubmission(
    tmp_path,
    fake_git_lfs: None,
) -> None:
    remote = tmp_path / "artifacts.git"
    first_factory = GitLFSRepositoryBackend.factory(
        remote,
        work_dir=tmp_path / "first-work",
        cache_dir=tmp_path / "first-cache",
    )

    first = RequestService(
        build_default_dispatcher(
            backend_factory=first_factory, scenario_storage=SQLiteScenarioStorage(), coordination=memory_coordination()
        )
    )
    first.accept({"x-aster-scenario": "durable"}, {"score": 1.0}, request_type=RequestType.REPORT)

    restarted_factory = GitLFSRepositoryBackend.factory(
        remote,
        work_dir=tmp_path / "restarted-work",
        cache_dir=tmp_path / "restarted-cache",
    )
    restarted_dispatcher = build_default_dispatcher(
        backend_factory=restarted_factory, scenario_storage=SQLiteScenarioStorage(), coordination=memory_coordination()
    )
    restarted = RequestService(restarted_dispatcher)
    restarted.accept(
        {"x-aster-scenario": "durable"},
        {"score": 0.5},
        request_type=RequestType.REPORT,
    )

    assert restarted_dispatcher.registry.get_optional("durable") is not None


@pytest.mark.unit
def test_different_scenarios_do_not_share_a_creation_lock(monkeypatch) -> None:
    dispatcher = build_default_dispatcher(scenario_storage=SQLiteScenarioStorage(), coordination=memory_coordination())
    load_or_create = dispatcher.registry._scenario_factory.load_or_create
    entered = Barrier(2)

    def load_or_create_together(scenario, release_id):
        entered.wait(timeout=2)
        return load_or_create(scenario, release_id)

    monkeypatch.setattr(dispatcher.registry._scenario_factory, "load_or_create", load_or_create_together)

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = (
            executor.submit(dispatcher.get_or_create_scenario, "first"),
            executor.submit(dispatcher.get_or_create_scenario, "second"),
        )
        scenarios = [future.result() for future in futures]

    assert {scenario.name for scenario in scenarios} == {"first", "second"}

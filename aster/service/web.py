"""The HTTP application that every Aster service serves: one constructor, so each service reads bodies of the same
size, authenticates the same way, translates errors the same way, and answers ``/healthz``."""

from __future__ import annotations

from collections.abc import Iterable

from aiohttp import web

from aster.service.auth import create_authentication_middleware
from aster.service.errors import translate_errors

#: The largest request body a service reads. aiohttp's default is 1 MiB, and a coding agent's first call carries
#: its whole context: Claude Code with a dozen MCP servers and a few hundred skills sends several MiB, which the
#: default answered with 413 and the agent reported as a request too large.
MAX_REQUEST_BYTES = 64 * 1024 * 1024


def service_application(
    tokens: str | Iterable[str] | None, *, evaluation_tokens: str | Iterable[str] | None = None
) -> web.Application:
    """An app behind the service ``tokens`` (and ``evaluation_tokens`` on the evaluation routes) that reads bodies of
    up to ``MAX_REQUEST_BYTES``, translates Aster's errors to HTTP statuses, and answers ``/healthz``, which needs no
    token."""
    app = web.Application(
        middlewares=[create_authentication_middleware(tokens, evaluation_tokens=evaluation_tokens), translate_errors],
        client_max_size=MAX_REQUEST_BYTES,
    )

    async def health(request: web.Request) -> web.Response:
        return web.json_response({"ok": True})

    app.router.add_get("/healthz", health)
    # Routes are registered as /aster/... The published client still calls /reef/...
    original_add_resource = app.router.add_resource

    def add_resource(path, *, name=None):
        resource = original_add_resource(path, name=name)
        if not isinstance(path, str) or not path.startswith("/aster/"):
            return resource
        legacy = original_add_resource("/reef/" + path[len("/aster/") :])
        original_add_route = resource.add_route

        def add_route(method, handler, **kwargs):
            route = original_add_route(method, handler, **kwargs)
            legacy.add_route(method, handler, **kwargs)
            return route

        resource.add_route = add_route
        return resource

    app.router.add_resource = add_resource
    return app


__all__ = ["MAX_REQUEST_BYTES", "service_application"]

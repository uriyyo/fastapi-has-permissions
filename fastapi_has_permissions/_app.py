from typing import cast

from fastapi import FastAPI, Response, WebSocket
from fastapi.exception_handlers import http_exception_handler
from fastapi_injected import add_injection
from fastapi_injected.fastapi import dependency_resolution_handler
from fastapi_injected.openapi import add_openapi
from starlette.requests import HTTPConnection, Request
from starlette.status import WS_1008_POLICY_VIOLATION
from starlette.types import ExceptionHandler

from ._errors import PermissionDeniedError


# the handler is reached from an HTTP route and from a websocket one alike, so it takes the
# connection both share and answers in the only way the protocol at hand allows
async def permission_denied_handler(connection: HTTPConnection, exc: Exception) -> Response | None:
    denied = cast("PermissionDeniedError", exc)

    if isinstance(connection, WebSocket):
        await connection.close(code=WS_1008_POLICY_VIOLATION, reason=denied.message)
        return None

    return await http_exception_handler(
        cast("Request", connection),
        denied.to_http_exception(),
    )


def add_permissions(app: FastAPI, /) -> None:
    add_injection(app)
    add_openapi(app)

    # starlette types a handler as either an HTTP one or a websocket one - this one serves both
    if PermissionDeniedError not in app.exception_handlers:
        app.add_exception_handler(PermissionDeniedError, cast("ExceptionHandler", permission_denied_handler))


__all__ = [
    "add_permissions",
    "dependency_resolution_handler",
    "permission_denied_handler",
]

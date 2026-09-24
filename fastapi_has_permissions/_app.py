from typing import cast

from fastapi import FastAPI, Response, WebSocket
from fastapi.exception_handlers import (
    http_exception_handler,
    request_validation_exception_handler,
    websocket_request_validation_exception_handler,
)
from fastapi.exceptions import WebSocketRequestValidationError
from fastapi_injected import DependencyResolutionError, add_injected_scope
from starlette.requests import HTTPConnection, Request
from starlette.status import WS_1008_POLICY_VIOLATION
from starlette.types import ExceptionHandler

from ._errors import PermissionDeniedError
from ._openapi import add_permissions_openapi


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


async def dependency_resolution_handler(connection: HTTPConnection, exc: Exception) -> Response | None:
    unresolved = cast("DependencyResolutionError", exc)

    if isinstance(connection, WebSocket):
        await websocket_request_validation_exception_handler(
            connection,
            WebSocketRequestValidationError(unresolved.errors),
        )
        return None

    return await request_validation_exception_handler(
        cast("Request", connection),
        unresolved.as_validation_error(),
    )


def add_permissions(app: FastAPI, /) -> None:
    add_injected_scope(app)
    add_permissions_openapi(app)
    # starlette types a handler as either an HTTP one or a websocket one - these serve both
    app.add_exception_handler(PermissionDeniedError, cast("ExceptionHandler", permission_denied_handler))
    app.add_exception_handler(DependencyResolutionError, cast("ExceptionHandler", dependency_resolution_handler))


__all__ = [
    "add_permissions",
    "dependency_resolution_handler",
    "permission_denied_handler",
]

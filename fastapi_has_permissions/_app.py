from typing import cast

from fastapi import FastAPI, Request, Response
from fastapi.exception_handlers import http_exception_handler
from fastapi_injected import add_injected_scope

from ._errors import PermissionDeniedError
from ._openapi import add_permissions_openapi


async def permission_denied_handler(request: Request, exc: Exception) -> Response:
    return await http_exception_handler(
        request,
        cast("PermissionDeniedError", exc).to_http_exception(),
    )


def add_permissions(app: FastAPI, /) -> None:
    add_injected_scope(app)
    add_permissions_openapi(app)
    app.add_exception_handler(PermissionDeniedError, permission_denied_handler)


__all__ = [
    "add_permissions",
    "permission_denied_handler",
]

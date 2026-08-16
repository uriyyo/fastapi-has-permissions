from fastapi import FastAPI
from fastapi_injected import add_injected_scope

from ._openapi import add_permissions_openapi


def add_permissions(app: FastAPI, /) -> None:
    add_injected_scope(app)
    add_permissions_openapi(app)


__all__ = [
    "add_permissions",
]

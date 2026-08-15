from fastapi import FastAPI
from fastapi_injected import add_injected_scope


def add_permissions(app: FastAPI, /) -> None:
    add_injected_scope(app)


__all__ = [
    "add_permissions",
]

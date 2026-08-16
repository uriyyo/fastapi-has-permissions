from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

from fastapi import APIRouter, FastAPI
from fastapi.openapi.utils import get_openapi
from fastapi.routing import APIRoute, iter_route_contexts

from .types import HasLazyDepends

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from fastapi.params import Depends


def route_declarations(route: Any, /) -> Iterator[Depends]:
    dependant = getattr(route, "dependant", None)

    if dependant is None:
        return

    methods = route.methods or ()

    for sub in dependant.dependencies:
        if isinstance(sub.call, HasLazyDepends):
            yield from sub.call.__lazy_depends__(methods)


def _documented_app(app: FastAPI, /) -> FastAPI:
    documented = FastAPI(openapi_url=None, docs_url=None, redoc_url=None)

    for route in iter_route_contexts(app.routes):
        original = route.original_route

        if not isinstance(original, APIRoute):
            continue

        dependencies = [*route_declarations(route)]

        path = route.path or original.path
        prefix = path[: -len(original.path)] if path.endswith(original.path) else ""

        documented.include_router(
            APIRouter(routes=[original]),
            prefix=prefix,
            dependencies=dependencies,
        )

    return documented


def build_permission_schema(app: FastAPI, /) -> dict[str, Any]:
    return get_openapi(
        title=app.title,
        version=app.version,
        openapi_version=app.openapi_version,
        summary=app.summary,
        description=app.description,
        terms_of_service=app.terms_of_service,
        contact=app.contact,
        license_info=app.license_info,
        routes=_documented_app(app).routes,
        webhooks=app.webhooks.routes,
        tags=app.openapi_tags,
        servers=app.servers,
        separate_input_output_schemas=app.separate_input_output_schemas,
        external_docs=app.openapi_external_docs,
    )


@dataclass
class _PermissionSchema:
    app: FastAPI
    wrapped: Callable[[], dict[str, Any]]
    source: dict[str, Any] | None = None
    schema: dict[str, Any] | None = None

    def __call__(self) -> dict[str, Any]:
        if self.wrapped() is not self.source:
            self.schema = build_permission_schema(self.app)
            self.app.openapi_schema = self.schema
            self.source = self.schema

        return cast("dict[str, Any]", self.schema)


def add_permissions_openapi(app: FastAPI, /) -> None:
    if isinstance(app.openapi, _PermissionSchema):
        return

    app.openapi = _PermissionSchema(app, app.openapi)  # type: ignore[ty:invalid-assignment]


__all__ = [
    "add_permissions_openapi",
    "build_permission_schema",
    "route_declarations",
]

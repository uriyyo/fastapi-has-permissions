from typing import Annotated, Any

import pytest
from fastapi import APIRouter, Depends, FastAPI, Header, status
from fastapi.routing import iter_route_contexts
from fastapi.security import OAuth2PasswordBearer
from fastapi.testclient import TestClient

from fastapi_has_permissions import (
    AllowSkipped,
    Dep,
    DepFactory,
    Permission,
    Policy,
    Requires,
    add_permissions,
)
from fastapi_has_permissions._openapi import build_permission_schema, route_declarations
from fastapi_has_permissions.common import Allow, HasScope

CHECKS: list[str] = []


class NeedsActor(Permission):
    async def check_permissions(self, x_actor: Annotated[str, Header()] = "ok") -> bool:
        CHECKS.append("x-actor")
        return x_actor == "ok"


class NeedsOther(Permission):
    async def check_permissions(self, x_other: Annotated[str, Header()] = "d") -> bool:
        return bool(x_other)


class IsAdmin(Permission):
    role_dep: Dep[str]

    async def check_permissions(self, role: str, /) -> bool:
        return role == "admin"


async def get_role(x_role: Annotated[str, Header()] = "guest") -> str:
    return x_role


RoleDep = DepFactory[str, get_role]

oauth = OAuth2PasswordBearer(tokenUrl="token", scopes={"read": "Read", "write": "Write"})


async def get_scopes(token: Annotated[str, Depends(oauth)]) -> list[str]:
    return ["read", "write"] if token else []


ScopeDep = DepFactory[list, get_scopes]


class Doc:
    def __init__(self, name: str) -> None:
        self.name = name


async def get_doc(x_doc: Annotated[str, Header()] = "d") -> Doc:
    return Doc(x_doc)


DocDep = DepFactory[Doc, get_doc]


class DocPolicy(Policy[Doc]):
    read = NeedsActor()
    delete = NeedsOther()

    __resource__ = DocDep


def declared_permission_name(dependency: Any) -> str:
    """Name of the permission a declaration resolves, or the callable's own name."""
    resolver = dependency.dependency

    return type(getattr(resolver, "permission", resolver)).__name__


def params(spec: dict[str, Any], path: str, method: str = "get") -> list[str]:
    return sorted(param["name"] for param in spec["paths"][path][method].get("parameters", []))


async def get_strict_doc(x_strict: Annotated[str, Header()]) -> Doc:
    return Doc(x_strict)


StrictDocDep = DepFactory[Doc, get_strict_doc]


def _add_policy_routes(application: FastAPI) -> None:
    @application.get("/strict-loader")
    async def strict_loader(doc: Annotated[Doc, Requires(StrictDocDep, Allow())]) -> str:
        return doc.name

    @application.get("/requires")
    async def requires(doc: Annotated[Doc, Requires(DocDep, IsAdmin(RoleDep))]) -> str:
        return doc.name

    @application.get("/policy", dependencies=[Depends(DocPolicy())])
    async def policy_get() -> str:
        return "ok"

    @application.delete("/policy", dependencies=[Depends(DocPolicy())])
    async def policy_delete() -> str:
        return "ok"

    router = APIRouter()

    @router.get("/nested", dependencies=[Depends(NeedsActor() & Allow())])
    async def nested() -> str:
        return "ok"

    application.include_router(router, prefix="/sub")


@pytest.fixture(scope="module")
def app() -> FastAPI:
    application = FastAPI()
    add_permissions(application)

    @application.get("/root", dependencies=[Depends(NeedsActor())])
    async def root() -> str:
        return "ok"

    @application.get("/composed", dependencies=[Depends(NeedsActor() & NeedsOther())])
    async def composed() -> str:
        return "ok"

    @application.get("/negated", dependencies=[Depends(~NeedsActor())])
    async def negated() -> str:
        return "ok"

    @application.get("/wrapped", dependencies=[Depends(AllowSkipped(NeedsActor()))])
    async def wrapped() -> str:
        return "ok"

    @application.get("/repeated", dependencies=[Depends(NeedsActor() & NeedsActor())])
    async def repeated() -> str:
        return "ok"

    @application.get("/scoped", dependencies=[Depends(HasScope(ScopeDep, ["read", "write"]) & Allow())])
    async def scoped() -> str:
        return "ok"

    @application.get("/own-param", dependencies=[Depends(NeedsActor())])
    async def own_param(q: str = "d") -> str:
        return q

    _add_policy_routes(application)

    return application


@pytest.fixture(scope="module")
def spec(app: FastAPI) -> dict[str, Any]:
    return app.openapi()


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        pytest.param("/root", ["x-actor"], id="leaf"),
        pytest.param("/composed", ["x-actor", "x-other"], id="both-branches-of-a-composite"),
        pytest.param("/negated", ["x-actor"], id="negated"),
        pytest.param("/wrapped", ["x-actor"], id="through-a-wrapper"),
        pytest.param("/sub/nested", ["x-actor"], id="included-router"),
        pytest.param("/requires", ["x-doc", "x-role"], id="requires-permission-and-loader"),
    ],
)
def test_permission_parameters_are_documented(spec: dict[str, Any], path: str, expected: list[str]) -> None:
    assert params(spec, path) == expected


def test_a_repeated_permission_is_documented_once(spec: dict[str, Any]) -> None:
    assert params(spec, "/repeated") == ["x-actor"]


def test_the_routes_own_parameters_are_kept(spec: dict[str, Any]) -> None:
    assert params(spec, "/own-param") == ["q", "x-actor"]


def test_security_scopes_and_schemes_reach_the_schema(spec: dict[str, Any]) -> None:
    [requirement] = spec["paths"]["/scoped"]["get"]["security"]

    # scopes come out of a set, so their order is not meaningful
    assert sorted(requirement["OAuth2PasswordBearer"]) == ["read", "write"]
    assert "OAuth2PasswordBearer" in spec["components"]["securitySchemes"]


def test_a_policy_documents_only_the_action_matching_the_method(spec: dict[str, Any]) -> None:
    # GET maps to `read` and DELETE to `delete`, so neither should advertise the other's
    assert params(spec, "/policy", "get") == ["x-actor"]
    assert params(spec, "/policy", "delete") == ["x-other"]


class TestDocumentingIsInert:
    # the whole design rests on the documented-only app never serving anything

    def test_generating_the_schema_runs_no_check(self, app: FastAPI) -> None:
        CHECKS.clear()
        app.openapi_schema = None
        app.openapi()

        assert CHECKS == []

    def test_a_request_runs_the_check_exactly_once(self, app: FastAPI) -> None:
        app.openapi()
        CHECKS.clear()

        with TestClient(app) as test_client:
            test_client.get("/root", headers={"x-actor": "ok"})

        assert CHECKS == ["x-actor"]

    @pytest.mark.parametrize(
        ("actor", "expected_status"),
        [
            pytest.param("ok", status.HTTP_200_OK, id="allowed"),
            pytest.param("no", status.HTTP_403_FORBIDDEN, id="denied"),
        ],
    )
    def test_enforcement_is_unchanged(self, app: FastAPI, actor: str, expected_status: int) -> None:
        with TestClient(app) as test_client:
            response = test_client.get("/composed", headers={"x-actor": actor})

        assert response.status_code == expected_status


class TestCaching:
    # generation piggybacks on FastAPI's own caching rather than reimplementing it

    def test_repeated_calls_reuse_the_cached_schema(self, app: FastAPI) -> None:
        first, second = app.openapi(), app.openapi()

        assert first is second
        assert params(second, "/root") == ["x-actor"]

    def test_a_route_added_later_is_documented(self) -> None:
        application = FastAPI()
        add_permissions(application)

        @application.get("/early", dependencies=[Depends(NeedsActor())])
        async def early() -> str:
            return "ok"

        application.openapi()

        @application.get("/late", dependencies=[Depends(NeedsOther())])
        async def late() -> str:
            return "ok"

        spec = application.openapi()

        assert params(spec, "/early") == ["x-actor"]
        assert params(spec, "/late") == ["x-other"]


class TestInstallation:
    def test_is_idempotent(self) -> None:
        application = FastAPI()
        add_permissions(application)
        installed = application.openapi
        add_permissions(application)

        assert application.openapi is installed

    def test_a_custom_openapi_installed_first_is_superseded(self) -> None:
        # the wrapped implementation is called for its caching, not its output, so a
        # custom one installed beforehand does not survive - build on
        # `build_permission_schema` instead, as the next test shows
        application = FastAPI()

        def custom() -> dict[str, Any]:
            schema = FastAPI.openapi(application)
            schema["info"]["x-custom"] = True
            return schema

        application.openapi = custom  # type: ignore[ty:invalid-assignment]
        add_permissions(application)

        @application.get("/x", dependencies=[Depends(NeedsActor())])
        async def route() -> str:
            return "ok"

        spec = application.openapi()

        assert "x-custom" not in spec["info"]
        assert params(spec, "/x") == ["x-actor"]

    def test_build_permission_schema_composes_with_a_custom_openapi(self) -> None:
        application = FastAPI()
        add_permissions(application)

        @application.get("/x", dependencies=[Depends(NeedsActor())])
        async def route() -> str:
            return "ok"

        def custom() -> dict[str, Any]:
            schema = build_permission_schema(application)
            schema["info"]["x-custom"] = True
            return schema

        application.openapi = custom  # type: ignore[ty:invalid-assignment]
        spec = application.openapi()

        assert spec["info"]["x-custom"] is True
        assert params(spec, "/x") == ["x-actor"]

    def test_an_app_without_permissions_is_unaffected(self) -> None:
        plain, wrapped = FastAPI(), FastAPI()

        for application in (plain, wrapped):

            @application.get("/x")
            async def route(q: str = "d") -> str:
                return q

        add_permissions(wrapped)

        assert wrapped.openapi()["paths"] == plain.openapi()["paths"]


class TestLazyDepends:
    # every kind of guard says for itself what a caller has to supply, so nothing else
    # needs to know the difference between them

    def test_a_leaf_declares_itself(self) -> None:
        permission = NeedsActor()

        assert [declared_permission_name(d) for d in permission.__lazy_depends__()] == ["NeedsActor"]

    def test_a_composite_declares_every_branch(self) -> None:
        declared = [declared_permission_name(d) for d in (NeedsActor() & NeedsOther()).__lazy_depends__()]

        assert declared[1:] == ["NeedsActor", "NeedsOther"]

    def test_a_wrapper_declares_its_child(self) -> None:
        declared = [declared_permission_name(d) for d in AllowSkipped(NeedsActor()).__lazy_depends__()]

        assert "NeedsActor" in declared

    def test_a_policy_declares_the_action_for_the_method(self) -> None:
        policy = DocPolicy()

        assert [declared_permission_name(d) for d in policy.__lazy_depends__(["GET"])] == ["NeedsActor"]
        assert [declared_permission_name(d) for d in policy.__lazy_depends__(["DELETE"])] == ["NeedsOther"]

    def test_a_route_declares_each_branch_of_its_composite(self, app: FastAPI) -> None:
        route = next(r for r in iter_route_contexts(app.routes) if r.path == "/composed")
        declared = {declared_permission_name(dependency) for dependency in route_declarations(route)}

        assert {"NeedsActor", "NeedsOther"} <= declared

    def test_a_requires_route_declares_its_loader_and_permission(self, app: FastAPI) -> None:
        route = next(r for r in iter_route_contexts(app.routes) if r.path == "/requires")
        declared = [dependency.dependency for dependency in route_declarations(route)]

        # the loader is a plain callable; the permission arrives via its resolver
        assert get_doc in declared
        assert any(getattr(d, "permission", None).__class__.__name__ == "IsAdmin" for d in declared)

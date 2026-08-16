from collections.abc import Iterator
from dataclasses import dataclass, is_dataclass
from typing import Annotated, Any, ClassVar

import pytest
from fastapi import FastAPI, Header, params, status
from fastapi.testclient import TestClient

from fastapi_has_permissions import Dep, DepFactory, Permission, Policy, Requires, add_permissions, skip
from fastapi_has_permissions.common import Allow, Deny


@dataclass
class Doc:
    name: str


LOADER_CALLS: list[str] = []
HANDLER_CALLS: list[str] = []


async def get_doc(x_name: Annotated[str, Header()] = "doc") -> Doc:
    LOADER_CALLS.append(x_name)
    return Doc(name=x_name)


async def get_role(x_role: Annotated[str, Header()] = "user") -> str:
    return x_role


DocDep = DepFactory[Doc, get_doc]
RoleDep = DepFactory[str, get_role]


class Masked(Deny):
    default_exc_message: ClassVar[str] = "no such doc"
    default_exc_status_code: ClassVar[int] = status.HTTP_404_NOT_FOUND
    default_exc_code: ClassVar[str] = "gone"


class Skipper(Permission):
    async def check_permissions(self) -> bool:
        skip("no opinion")


class IsAdmin(Permission):
    role_dep: Dep[str]

    async def check_permissions(self, role: str, /) -> bool:
        return role == "admin"


class ReadOnly(Policy[Doc]):
    read = Allow()
    publish = Deny()
    archive = Allow()

    __resource__ = DocDep


app = FastAPI()
add_permissions(app)


@app.get("/allow")
async def allow(doc: Annotated[Doc, Requires(DocDep, Allow())]) -> Any:
    HANDLER_CALLS.append(doc.name)
    return {"name": doc.name}


@app.get("/deny")
async def deny(doc: Annotated[Doc, Requires(DocDep, Deny())]) -> Any:
    HANDLER_CALLS.append(doc.name)
    return {"name": doc.name}


@app.get("/masked")
async def masked(doc: Annotated[Doc, Requires(DocDep, Masked())]) -> Any:
    return {"name": doc.name}


@app.get("/skip")
async def skipped(doc: Annotated[Doc, Requires(DocDep, Skipper())]) -> Any:
    return {"name": doc.name}


# a loader whose own input the caller must supply, and which has no default
async def get_strict_doc(x_strict: Annotated[str, Header()]) -> Doc:
    return Doc(name=x_strict)


StrictDocDep = DepFactory[Doc, get_strict_doc]


@app.get("/strict-loader")
async def strict_loader(doc: Annotated[Doc, Requires(StrictDocDep, Allow())]) -> Any:
    return {"name": doc.name}


@app.get("/with-deps")
async def with_deps(doc: Annotated[Doc, Requires(DocDep, IsAdmin(RoleDep))]) -> Any:
    return {"name": doc.name}


@app.get("/composed")
async def composed(doc: Annotated[Doc, Requires(DocDep, IsAdmin(RoleDep) | Allow())]) -> Any:
    return {"name": doc.name}


@app.get("/twice")
async def twice(
    first: Annotated[Doc, Requires(DocDep, Allow())],
    second: Annotated[Doc, Requires(DocDep, Allow())],
) -> Any:
    return {"same": first == second}


# a policy in the permission slot dispatches on the request method and injects the resource
@app.get("/policy")
async def via_policy_get(doc: Annotated[Doc, Requires(DocDep, ReadOnly())]) -> Any:
    return {"name": doc.name}


@app.post("/policy")
async def via_policy_post(doc: Annotated[Doc, Requires(DocDep, ReadOnly())]) -> Any:
    return {"name": doc.name}


# single-argument form: the policy supplies both the check and the resource
@app.get("/policy-only")
async def via_policy_only_get(doc: Annotated[Doc, Requires(ReadOnly())]) -> Any:
    return {"name": doc.name}


@app.post("/policy-only")
async def via_policy_only_post(doc: Annotated[Doc, Requires(ReadOnly())]) -> Any:
    return {"name": doc.name}


# a named action: the policy supplies the resource, the permission names what to check
@app.post("/publish")
async def publish(doc: Annotated[Doc, Requires(ReadOnly(), ReadOnly.publish)]) -> Any:
    return {"name": doc.name}


@app.post("/archive")
async def archive(doc: Annotated[Doc, Requires(ReadOnly(), ReadOnly.archive)]) -> Any:
    return {"name": doc.name}


@pytest.fixture(scope="session")
def app_client() -> Iterator[TestClient]:
    with TestClient(app) as client:
        yield client


@pytest.fixture(autouse=True)
def _reset() -> None:
    LOADER_CALLS.clear()
    HANDLER_CALLS.clear()


def test_resource_is_injected(app_client: TestClient) -> None:
    response = app_client.get("/allow", headers={"x-name": "hello"})

    assert response.status_code == status.HTTP_200_OK
    # the handler receives the resource, not the CheckResult
    assert response.json() == {"name": "hello"}


def test_denied_request_never_reaches_the_handler(app_client: TestClient) -> None:
    response = app_client.get("/deny")

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert HANDLER_CALLS == []


def test_resource_is_resolved_once(app_client: TestClient) -> None:
    app_client.get("/allow", headers={"x-name": "hello"})

    assert LOADER_CALLS == ["hello"]


def test_resource_is_not_resolved_when_denied(app_client: TestClient) -> None:
    # the permission is resolved first, so a denial never pays for the load
    app_client.get("/deny")

    assert LOADER_CALLS == []


def test_error_config_propagates_from_the_permission(app_client: TestClient) -> None:
    response = app_client.get("/masked")

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["detail"] == {"code": "gone", "message": "no such doc"}


def test_a_loader_validation_error_is_a_422() -> None:
    # the loader reads the request too, so a parameter it is missing is the caller's
    # mistake - not a crash
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/strict-loader")

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert response.json()["detail"][0]["loc"] == ["header", "x-strict"]


def test_skip_denies(app_client: TestClient) -> None:
    assert app_client.get("/skip").status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.parametrize(
    ("role", "expected"),
    [
        pytest.param("admin", status.HTTP_200_OK, id="admin"),
        pytest.param("user", status.HTTP_403_FORBIDDEN, id="user"),
    ],
)
def test_permission_dependencies_are_resolved(app_client: TestClient, role: str, expected: int) -> None:
    assert app_client.get("/with-deps", headers={"x-role": role}).status_code == expected


def test_composed_permissions_work(app_client: TestClient) -> None:
    assert app_client.get("/composed", headers={"x-role": "user"}).status_code == status.HTTP_200_OK


def test_two_requires_share_the_resolved_resource(app_client: TestClient) -> None:
    response = app_client.get("/twice", headers={"x-name": "hello"})

    assert response.json() == {"same": True}
    assert LOADER_CALLS == ["hello"]


class TestWithAPolicy:
    @pytest.mark.parametrize(
        ("method", "expected"),
        [
            pytest.param("GET", status.HTTP_200_OK, id="read-allowed"),
            pytest.param("POST", status.HTTP_403_FORBIDDEN, id="create-denied"),
        ],
    )
    def test_policy_dispatches_on_the_request_method(
        self,
        app_client: TestClient,
        method: str,
        expected: int,
    ) -> None:
        assert app_client.request(method, "/policy", headers={"x-name": "hello"}).status_code == expected

    def test_policy_injects_the_resource(self, app_client: TestClient) -> None:
        assert app_client.get("/policy", headers={"x-name": "hello"}).json() == {"name": "hello"}

    def test_single_argument_form_uses_the_policy_resource(self, app_client: TestClient) -> None:
        assert app_client.get("/policy-only", headers={"x-name": "hello"}).json() == {"name": "hello"}

    def test_single_argument_form_still_dispatches(self, app_client: TestClient) -> None:
        assert app_client.request("POST", "/policy-only").status_code == status.HTTP_403_FORBIDDEN

    def test_single_argument_form_wires_both_sides(self) -> None:
        policy = ReadOnly()
        requires = Requires(policy)

        assert requires.dependency.resource_dep is DocDep
        assert requires.dependency.requirement is policy

    def test_a_named_action_overrides_method_dispatch(self, app_client: TestClient) -> None:
        # POST would map to `create` (Deny), but the named action wins
        assert app_client.post("/archive", headers={"x-name": "hello"}).status_code == status.HTTP_200_OK

    def test_a_named_action_is_still_enforced(self, app_client: TestClient) -> None:
        assert app_client.post("/publish").status_code == status.HTTP_403_FORBIDDEN

    def test_a_named_action_uses_the_policy_resource(self, app_client: TestClient) -> None:
        assert app_client.post("/archive", headers={"x-name": "hello"}).json() == {"name": "hello"}

    def test_a_named_action_wires_both_sides(self) -> None:
        requires = Requires(ReadOnly(), ReadOnly.archive)

        assert requires.dependency.resource_dep is DocDep
        assert requires.dependency.requirement is ReadOnly.archive

    def test_a_policy_class_is_rejected(self) -> None:
        # a type error too, but the runtime guard is what an unchecked caller hits
        with pytest.raises(TypeError, match="takes a policy instance, not the class"):
            Requires(ReadOnly)  # type: ignore[ty:invalid-argument-type]

    def test_a_bare_resource_dependency_is_rejected(self) -> None:
        with pytest.raises(TypeError, match="needs a permission or a policy"):
            Requires(DocDep)  # type: ignore[ty:invalid-argument-type]

    def test_a_plain_function_resource_is_not_bound_to_the_policy(self) -> None:
        # a function assigned in the class body must not arrive as a bound method,
        # or the loader would receive the policy as its first argument
        async def load(x_name: Annotated[str, Header()] = "doc") -> Doc:
            return Doc(name=x_name)

        class RawPolicy(Policy[Doc]):
            read = Allow()

            __resource__ = load

        raw_app = FastAPI()
        add_permissions(raw_app)

        @raw_app.get("/raw")
        async def route(doc: Annotated[Doc, Requires(RawPolicy())]) -> Any:
            return {"name": doc.name}

        with TestClient(raw_app) as client:
            assert client.get("/raw", headers={"x-name": "bob"}).json() == {"name": "bob"}

    def test_default_resource_resolves_to_none(self) -> None:
        class Bare(Policy[Any]):
            read = Allow()

        bare_app = FastAPI()
        add_permissions(bare_app)

        @bare_app.get("/bare")
        async def route(value: Annotated[Any, Requires(Bare())]) -> Any:
            return {"value": value}

        with TestClient(bare_app) as client:
            assert client.get("/bare").json() == {"value": None}


def test_requires_returns_a_dependency() -> None:
    # usable straight inside `Annotated[...]`, no `Depends()` wrapper needed
    requires = Requires(DocDep, Allow())

    assert isinstance(requires, params.Depends)
    assert is_dataclass(requires.dependency)


def test_use_cache_is_forwarded() -> None:
    assert Requires(DocDep, Allow()).use_cache is True
    assert Requires(DocDep, Allow(), use_cache=False).use_cache is False


def test_use_cache_is_forwarded_for_the_policy_form() -> None:
    assert Requires(ReadOnly(), use_cache=False).use_cache is False


def test_requires_wires_its_fields_positionally() -> None:
    requires = Requires(DocDep, Allow())

    assert requires.dependency.resource_dep is DocDep
    assert isinstance(requires.dependency.requirement, Allow)


def test_both_the_permission_and_the_loader_are_documented() -> None:
    # the loader reads the request just as the permission does, so what it needs is the
    # caller's to supply and belongs in the schema too
    parameters = app.openapi()["paths"]["/with-deps"]["get"]["parameters"]

    assert sorted(param["name"] for param in parameters) == ["x-name", "x-role"]

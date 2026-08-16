from collections.abc import Iterator
from dataclasses import dataclass, is_dataclass
from typing import Annotated, Any, ClassVar

import pytest
from fastapi import APIRouter, Depends, FastAPI, Header, Path, status
from fastapi.testclient import TestClient

from fastapi_has_permissions import DepFactory, Permission, Policy, add_permissions, skip
from fastapi_has_permissions.common import Allow, Deny


@dataclass
class Doc:
    name: str


async def get_doc(x_name: Annotated[str, Header()] = "doc") -> Doc:
    return Doc(name=x_name)


DocDep = DepFactory[Doc, get_doc]

READ_METHODS = ["GET", "QUERY", "HEAD"]
WRITE_METHODS = ["POST", "PUT", "PATCH", "DELETE"]
UNMAPPED_METHODS = ["OPTIONS", "TRACE"]
ALL_METHODS = [*READ_METHODS, *WRITE_METHODS, *UNMAPPED_METHODS]


class Masked(Deny):
    default_exc_message: ClassVar[str] = "no such doc"
    default_exc_status_code: ClassVar[int] = status.HTTP_404_NOT_FOUND
    default_exc_code: ClassVar[str] = "gone"
    default_exc_headers: ClassVar[dict[str, str] | None] = {"X-Reason": "masked"}


class Skipper(Permission):
    async def check_permissions(self) -> bool:
        skip("no opinion")


class AllowAll(Policy[Doc]):
    read = Allow()
    create = Allow()
    update = Allow()
    delete = Allow()
    default = Allow()

    __resource__ = DocDep


class ReadOnly(Policy[Doc]):
    read = Allow()

    __resource__ = DocDep


class DenyAll(Policy[Doc]):
    __resource__ = DocDep


class MaskedPolicy(Policy[Doc]):
    read = Masked()


class SkipPolicy(Policy[Doc]):
    read = Skipper()


class ComposedPolicy(Policy[Doc]):
    read = Allow() | Deny()
    update = Allow() & Deny()


app = FastAPI()
add_permissions(app)


def _register(path: str, policy: Policy[Doc]) -> None:
    # a policy is a gate: it checks and returns nothing
    async def route(_: Annotated[None, Depends(policy)]) -> Any:
        return {"ok": True}

    app.add_api_route(path, route, methods=ALL_METHODS)


_register("/allow", AllowAll())
_register("/readonly", ReadOnly())
_register("/deny", DenyAll())
_register("/masked", MaskedPolicy())
_register("/skip", SkipPolicy())
_register("/composed", ComposedPolicy())


@pytest.fixture(scope="session")
def app_client() -> Iterator[TestClient]:
    with TestClient(app) as client:
        yield client


@pytest.mark.parametrize(
    ("method", "expected"),
    [
        # GET / QUERY / HEAD map to `read`, the only action this policy allows
        pytest.param("GET", status.HTTP_200_OK, id="get-is-read"),
        pytest.param("QUERY", status.HTTP_200_OK, id="query-is-read"),
        pytest.param("HEAD", status.HTTP_200_OK, id="head-is-read"),
        pytest.param("POST", status.HTTP_403_FORBIDDEN, id="post-is-create"),
        pytest.param("PUT", status.HTTP_403_FORBIDDEN, id="put-is-update"),
        pytest.param("PATCH", status.HTTP_403_FORBIDDEN, id="patch-is-update"),
        pytest.param("DELETE", status.HTTP_403_FORBIDDEN, id="delete-is-delete"),
        # anything not named above falls through to `default`
        pytest.param("OPTIONS", status.HTTP_403_FORBIDDEN, id="options-is-default"),
        pytest.param("TRACE", status.HTTP_403_FORBIDDEN, id="trace-is-default"),
    ],
)
def test_method_maps_to_the_matching_action(app_client: TestClient, method: str, expected: int) -> None:
    assert app_client.request(method, "/readonly").status_code == expected


@pytest.mark.parametrize("method", ALL_METHODS)
def test_every_method_passes_when_all_actions_allow(app_client: TestClient, method: str) -> None:
    assert app_client.request(method, "/allow").status_code == status.HTTP_200_OK


@pytest.mark.parametrize("method", ALL_METHODS)
def test_a_bare_policy_denies_every_method(app_client: TestClient, method: str) -> None:
    # nothing is declared, so every action - including the fallback - is `Deny()`
    assert app_client.request(method, "/deny").status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.parametrize("name", ["read", "create", "update", "delete", "default"])
def test_every_action_defaults_to_deny(name: str) -> None:
    # secure by default: an unmapped method must not slip through unchecked
    assert isinstance(getattr(Policy, name), Deny)


def test_policy_is_a_gate_and_returns_nothing(app_client: TestClient) -> None:
    assert app_client.get("/readonly").json() == {"ok": True}


def test_error_config_propagates_from_the_action(app_client: TestClient) -> None:
    response = app_client.get("/masked")

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["detail"] == {"code": "gone", "message": "no such doc"}
    assert response.headers["x-reason"] == "masked"


def test_skip_at_the_root_denies(app_client: TestClient) -> None:
    # a skip is an abstention, not an approval
    assert app_client.get("/skip").status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.parametrize(
    ("method", "expected"),
    [
        pytest.param("GET", status.HTTP_200_OK, id="or-passes"),
        pytest.param("PUT", status.HTTP_403_FORBIDDEN, id="and-fails"),
    ],
)
def test_actions_may_be_composed_permissions(app_client: TestClient, method: str, expected: int) -> None:
    assert app_client.request(method, "/composed").status_code == expected


def test_subclass_overrides_a_single_action() -> None:
    class Stricter(ReadOnly):
        read = Deny()

    assert isinstance(Stricter.read, Deny)
    assert isinstance(ReadOnly.read, Allow)
    assert Stricter.create is ReadOnly.create


def test_subclass_inherits_the_resource() -> None:
    class Child(ReadOnly):
        pass

    assert Child.__resource__ is DocDep


def test_default_resource_is_used_when_none_is_declared() -> None:
    assert MaskedPolicy.__resource__ is Policy.__resource__


def test_a_gate_does_not_resolve_the_resource() -> None:
    # the resource is `Requires`' job, so a router-level gate works on routes that
    # cannot supply the loader's parameters
    async def by_id(doc_id: Annotated[int, Path()]) -> Doc:
        return Doc(name=str(doc_id))

    class ById(Policy[Doc]):
        read = Allow()

        __resource__ = DepFactory[Doc, by_id]

    gated_app = FastAPI()
    add_permissions(gated_app)
    router = APIRouter(dependencies=[Depends(ById())])

    @router.get("/items/{doc_id}")
    async def one(doc_id: int) -> Any:
        return {"id": doc_id}

    @router.get("/items")
    async def many() -> Any:
        return {"list": True}

    gated_app.include_router(router)

    with TestClient(gated_app) as client:
        assert client.get("/items/1").status_code == status.HTTP_200_OK
        assert client.get("/items").status_code == status.HTTP_200_OK


class TestBind:
    def test_returns_a_subclass(self) -> None:
        bound = MaskedPolicy.bind(DocDep)

        assert issubclass(bound, MaskedPolicy)
        assert bound.__resource__ is DocDep

    def test_leaves_the_original_untouched(self) -> None:
        MaskedPolicy.bind(DocDep)

        assert MaskedPolicy.__resource__ is not DocDep

    def test_keeps_the_actions(self) -> None:
        bound = ReadOnly.bind(DocDep)

        assert bound.read is ReadOnly.read
        assert isinstance(bound.delete, Deny)

    def test_each_call_returns_a_distinct_class(self) -> None:
        assert ReadOnly.bind(DocDep) is not ReadOnly.bind(DocDep)

    def test_bound_policy_gates_requests(self) -> None:
        bound_app = FastAPI()
        add_permissions(bound_app)

        @bound_app.get("/bound")
        async def route(_: Annotated[None, Depends(ReadOnly.bind(DocDep)())]) -> Any:
            return {"ok": True}

        with TestClient(bound_app) as client:
            assert client.get("/bound").json() == {"ok": True}


def test_policies_are_dataclasses() -> None:
    assert is_dataclass(Policy)


def test_policy_instances_compare_equal() -> None:
    assert ReadOnly() == ReadOnly()
    assert ReadOnly() != DenyAll()


def test_policy_instances_are_hashable() -> None:
    # required for use as a FastAPI dependency
    assert isinstance(hash(ReadOnly()), int)

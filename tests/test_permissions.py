from collections.abc import Iterator
from dataclasses import dataclass
from typing import Annotated

import pytest
from fastapi import Depends, FastAPI, Header, Request, status
from fastapi import Security as FastAPISecurity
from fastapi.testclient import TestClient

from fastapi_has_permissions import (
    AllPermissions,
    AnyPermissions,
    CheckResult,
    Dep,
    DepFactory,
    Eval,
    Permission,
    Security,
    add_permissions,
    evaluate,
)

from .future_annotations_perms import HasRoleFutureAnnotations

app = FastAPI()
add_permissions(app)


class HasAuthorizationHeader(Permission):
    async def check_permissions(self, request: Request) -> bool:
        return "Authorization" in request.headers


@dataclass
class HasRole(Permission):
    role: str

    async def check_permissions(self, request: Request) -> bool:
        return request.headers.get("role") == self.role


@app.get(
    "/simple-test",
    dependencies=[
        Depends(HasAuthorizationHeader()),
    ],
)
@app.get(
    "/and-test",
    dependencies=[
        Depends(HasAuthorizationHeader() & HasRole("admin")),
    ],
)
@app.get(
    "/or-test",
    dependencies=[
        Depends(HasAuthorizationHeader() | HasRole("admin")),
    ],
)
@app.get(
    "/not-test",
    dependencies=[
        Depends(~HasAuthorizationHeader()),
    ],
)
@app.get(
    "/complex-test",
    dependencies=[
        Depends((HasAuthorizationHeader() & HasRole("admin")) | ~HasRole("user")),
    ],
)
async def route() -> str:
    return "You have access to this endpoint!"


@app.get("/auto-error-test")
async def eval_route(
    *,
    has_auth: Eval[CheckResult, HasAuthorizationHeader()],
) -> dict[str, bool]:
    return {"has_auth": bool(has_auth)}


@pytest.fixture(scope="session")
def app_client() -> Iterator[TestClient]:
    with TestClient(app) as client:
        yield client


@pytest.mark.parametrize(
    ("endpoint", "headers", "expected_status"),
    [
        pytest.param(
            "/simple-test",
            {"Authorization": "some-token"},
            status.HTTP_200_OK,
            id="simple-test-pass",
        ),
        pytest.param(
            "/simple-test",
            {},
            status.HTTP_403_FORBIDDEN,
            id="simple-test-fail-no-auth-header",
        ),
        pytest.param(
            "/and-test",
            {"Authorization": "some-token", "role": "admin"},
            status.HTTP_200_OK,
            id="and-test-pass-both-satisfied",
        ),
        pytest.param(
            "/and-test",
            {"Authorization": "some-token"},
            status.HTTP_403_FORBIDDEN,
            id="and-test-fail-missing-role",
        ),
        pytest.param(
            "/and-test",
            {"role": "admin"},
            status.HTTP_403_FORBIDDEN,
            id="and-test-fail-missing-auth",
        ),
        pytest.param(
            "/and-test",
            {},
            status.HTTP_403_FORBIDDEN,
            id="and-test-fail-neither-satisfied",
        ),
        pytest.param(
            "/and-test",
            {"Authorization": "some-token", "role": "user"},
            status.HTTP_403_FORBIDDEN,
            id="and-test-fail-wrong-role",
        ),
        pytest.param(
            "/or-test",
            {"Authorization": "some-token", "role": "admin"},
            status.HTTP_200_OK,
            id="or-test-pass-both-satisfied",
        ),
        pytest.param(
            "/or-test",
            {"Authorization": "some-token"},
            status.HTTP_200_OK,
            id="or-test-pass-only-auth",
        ),
        pytest.param(
            "/or-test",
            {"role": "admin"},
            status.HTTP_200_OK,
            id="or-test-pass-only-role",
        ),
        pytest.param(
            "/or-test",
            {},
            status.HTTP_403_FORBIDDEN,
            id="or-test-fail-neither-satisfied",
        ),
        pytest.param(
            "/or-test",
            {"role": "user"},
            status.HTTP_403_FORBIDDEN,
            id="or-test-fail-wrong-role-no-auth",
        ),
        pytest.param(
            "/not-test",
            {},
            status.HTTP_200_OK,
            id="not-test-pass-no-auth-header",
        ),
        pytest.param(
            "/not-test",
            {"Authorization": "some-token"},
            status.HTTP_403_FORBIDDEN,
            id="not-test-fail-auth-header-present",
        ),
        pytest.param(
            "/complex-test",
            {"Authorization": "some-token", "role": "admin"},
            status.HTTP_200_OK,
            id="complex-test-pass-auth-and-admin",
        ),
        pytest.param(
            "/complex-test",
            {},
            status.HTTP_200_OK,
            id="complex-test-pass-no-role-satisfies-not-user",
        ),
        pytest.param(
            "/complex-test",
            {"role": "guest"},
            status.HTTP_200_OK,
            id="complex-test-pass-non-user-role-satisfies-not-user",
        ),
        pytest.param(
            "/complex-test",
            {"role": "user"},
            status.HTTP_403_FORBIDDEN,
            id="complex-test-fail-user-role-without-auth",
        ),
        pytest.param(
            "/complex-test",
            {"Authorization": "some-token", "role": "user"},
            status.HTTP_403_FORBIDDEN,
            id="complex-test-fail-auth-with-user-role-not-admin",
        ),
    ],
)
def test_permissions(endpoint, headers, expected_status, app_client) -> None:
    response = app_client.get(endpoint, headers=headers)
    assert response.status_code == expected_status


@pytest.mark.parametrize(
    ("headers", "expected_has_auth"),
    [
        pytest.param(
            {},
            False,
            id="auto-error-false-no-auth-header",
        ),
        pytest.param(
            {
                "Authorization": "some-token",
            },
            True,
            id="auto-error-false-with-auth-header",
        ),
    ],
)
def test_eval_returns_the_result(headers, expected_has_auth, app_client) -> None:
    response = app_client.get("/auto-error-test", headers=headers)
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"has_auth": expected_has_auth}


def test_flattening_is_associative() -> None:
    a, b, c = HasRole("a"), HasRole("b"), HasRole("c")

    assert (a | b) | c == AnyPermissions([a, b, c])
    assert a | (b | c) == AnyPermissions([a, b, c])
    assert (a & b) & c == AllPermissions([a, b, c])
    assert a & (b & c) == AllPermissions([a, b, c])


def test_flattening_does_not_mix_operators() -> None:
    a, b, c = HasRole("a"), HasRole("b"), HasRole("c")

    assert a & (b | c) == AllPermissions([a, AnyPermissions([b, c])])
    assert a | (b & c) == AnyPermissions([a, AllPermissions([b, c])])


@pytest.mark.parametrize(
    "configured",
    [
        pytest.param(AnyPermissions([HasRole("a"), HasRole("b")], message="custom"), id="message"),
        pytest.param(
            AnyPermissions([HasRole("a"), HasRole("b")], status_code=status.HTTP_404_NOT_FOUND),
            id="status-code",
        ),
        pytest.param(AnyPermissions([HasRole("a"), HasRole("b")], code="custom_code"), id="code"),
    ],
)
def test_configured_composite_is_not_flattened_away(configured) -> None:
    other = HasRole("c")

    assert (configured | other) == AnyPermissions([configured, other])
    assert (other | configured) == AnyPermissions([other, configured])


def test_plain_composite_is_flattened() -> None:
    plain = AnyPermissions([HasRole("a"), HasRole("b")])
    other = HasRole("c")

    assert (plain | other) == AnyPermissions([*plain.permissions, other])


def test_permissions_hash() -> None:
    assert HasRole("admin") == HasRole("admin")
    assert hash(HasRole("admin")) == hash(HasRole("admin"))


def test_hashable_fields_hash_by_value() -> None:
    class ValueHashed(Permission):
        role: str

        async def check_permissions(self) -> bool:
            return True

    assert ValueHashed("admin") == ValueHashed("admin")
    assert hash(ValueHashed("admin")) == hash(ValueHashed("admin"))


def test_unhashable_fields_fall_back_to_identity_hash() -> None:
    class Unhashable(Permission):
        roles: list[str]

        async def check_permissions(self) -> bool:
            return True

    permission = Unhashable(["admin"])

    assert hash(permission) == hash(permission)
    assert hash(Unhashable(["admin"])) != hash(permission)


def test_dataclass_kwargs_are_applied() -> None:
    class Ordered(Permission, order=True):
        level: int

        async def check_permissions(self) -> bool:
            return True

    assert Ordered(1) < Ordered(2)


class TestFutureAnnotations:
    @pytest.fixture
    def future_client(self) -> Iterator[TestClient]:
        async def get_role(role: Annotated[str, Header()] = "guest") -> str:
            return role

        future_app = FastAPI()
        add_permissions(future_app)

        permission = HasRoleFutureAnnotations(DepFactory[str, get_role])

        @future_app.get("/future", dependencies=[Depends(permission)])
        async def route() -> str:
            return "ok"

        with TestClient(future_app) as client:
            yield client

    def test_dep_field_is_recognized(self) -> None:
        async def get_role() -> str:
            return "admin"

        permission = HasRoleFutureAnnotations(DepFactory[str, get_role])

        assert len([*permission.__deps__()]) == 1

    @pytest.mark.parametrize(
        ("role", "expected_status"),
        [
            pytest.param("admin", status.HTTP_200_OK, id="allowed"),
            pytest.param("guest", status.HTTP_403_FORBIDDEN, id="denied"),
        ],
    )
    def test_permission_is_enforced(self, future_client: TestClient, role: str, expected_status: int) -> None:
        assert future_client.get("/future", headers={"role": role}).status_code == expected_status


class _Scoped(Permission):
    async def check_permissions(self) -> bool:
        return True


def test_security_normalises_list_scopes() -> None:
    class OurSecurity(_Scoped):
        def __resolver_to_depends__(self, resolver) -> object:
            return Security(resolver, scopes=["read", "write"])

    depends = next(iter(OurSecurity().__lazy_depends__()))

    assert depends.scopes == ("read", "write")
    assert hash(depends) == hash(next(iter(OurSecurity().__lazy_depends__())))


def test_fastapi_security_is_converted_to_ours() -> None:
    class FastAPIScoped(_Scoped):
        def __resolver_to_depends__(self, resolver) -> object:
            return FastAPISecurity(resolver, scopes=["read"])

    depends = next(iter(FastAPIScoped().__lazy_depends__()))

    assert isinstance(depends, Security)
    assert depends.scopes == ("read",)
    assert hash(depends) == hash(next(iter(FastAPIScoped().__lazy_depends__())))


class _BareCallableDep(Permission):
    role_dep: Dep

    async def check_permissions(self, role: str, /) -> bool:
        return role == "admin"


async def _get_role_value() -> str:
    return "admin"


@pytest.mark.asyncio
async def test_bare_callable_dep_field_resolves() -> None:
    # a plain callable is a dependency the same way `Resource` accepts one - without the
    # `Depends` wrap it used to land in annotation position and be read as a query param
    assert await evaluate(_BareCallableDep(_get_role_value)) is True
    assert await evaluate(_BareCallableDep(Depends(_get_role_value))) is True


def test_bare_callable_dep_field_serves_a_route() -> None:
    bare_app = FastAPI()
    add_permissions(bare_app)

    @bare_app.get("/bare", dependencies=[Depends(_BareCallableDep(_get_role_value))])
    async def _route() -> str:
        return "ok"

    with TestClient(bare_app) as client:
        assert client.get("/bare").status_code == status.HTTP_200_OK


def test_annotated_marker_dep_field_is_not_wrapped() -> None:
    # `Annotated[..., Path()]` is already an annotation - wrapping it in `Depends` would
    # make FastAPI call the annotation as if it were the dependency
    marker = Annotated[str, Header(alias="role")]

    class Marked(_BareCallableDep):
        pass

    sign = Marked(marker).__check_signature__()

    assert next(iter(sign.parameters.values())).annotation == marker


def test_more_deps_than_parameters_is_rejected() -> None:
    class TwoFieldsOneParam(Permission):
        first: Dep
        second: Dep

        async def check_permissions(self, _value: str, /) -> bool:
            return True

    permission = TwoFieldsOneParam(Depends(_get_role_value), Depends(_get_role_value))

    with pytest.raises(TypeError, match=r"2 dependencies cannot be bound to 1 parameters"):
        permission.__check_signature__()

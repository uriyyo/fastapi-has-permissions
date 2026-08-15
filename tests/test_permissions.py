from collections.abc import Iterator
from dataclasses import dataclass
from typing import Annotated

import pytest
from fastapi import Depends, FastAPI, Request, status
from fastapi.testclient import TestClient

from fastapi_has_permissions import AllPermissions, AnyPermissions, CheckResult, Permission, add_permissions
from fastapi_has_permissions.common import no_auto_error

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
async def auto_error_false_route(
    *,
    has_auth: Annotated[
        CheckResult,
        Depends(no_auto_error(HasAuthorizationHeader())),
    ],
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
def test_auto_error_false(headers, expected_has_auth, app_client) -> None:
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
        pytest.param(AnyPermissions([HasRole("a"), HasRole("b")], auto_error=False), id="auto-error"),
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


def test_permissions_hash_by_identity_by_default() -> None:
    assert HasRole("admin") == HasRole("admin")
    assert hash(HasRole("admin")) != hash(HasRole("admin"))


def test_no_hash_override_opts_out_of_identity_hash() -> None:
    class ValueHashed(Permission, no_hash_override=True, unsafe_hash=True):
        role: str

        async def check_permissions(self) -> bool:
            return True

    assert ValueHashed("admin") == ValueHashed("admin")
    assert hash(ValueHashed("admin")) == hash(ValueHashed("admin"))


def test_dataclass_kwargs_are_applied() -> None:
    class Ordered(Permission, order=True):
        level: int

        async def check_permissions(self) -> bool:
            return True

    assert Ordered(1) < Ordered(2)

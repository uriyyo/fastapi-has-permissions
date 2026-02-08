from collections.abc import Iterator
from typing import Annotated

import pytest
from fastapi import Depends, FastAPI, Header, status
from fastapi.testclient import TestClient
from starlette.requests import Request

from fastapi_has_permissions import Permission
from fastapi_has_permissions._func import FuncPermission, permission
from fastapi_has_permissions._results import CheckResult

app = FastAPI()


async def has_authorization_header(request: Request) -> CheckResult:
    return "authorization" in request.headers


async def has_role(role: Annotated[str, Header()]) -> CheckResult:
    return role == "admin"


has_authorization = permission(has_authorization_header)
has_admin_role = permission(has_role)


@app.get(
    "/simple-test",
    dependencies=[Depends(has_authorization)],
)
@app.get(
    "/and-test",
    dependencies=[Depends(has_authorization & has_admin_role)],
)
@app.get(
    "/or-test",
    dependencies=[Depends(has_authorization | has_admin_role)],
)
@app.get(
    "/not-test",
    dependencies=[Depends(~has_authorization)],
)
@app.get(
    "/complex-test",
    dependencies=[Depends((has_authorization & has_admin_role) | ~has_authorization)],
)
async def route():
    return "OK"


@pytest.fixture(scope="session")
def app_client() -> Iterator[TestClient]:
    with TestClient(app) as client:
        yield client


@pytest.mark.parametrize(
    ("endpoint", "headers", "expected_status"),
    [
        pytest.param(
            "/simple-test",
            {"authorization": "Bearer token"},
            status.HTTP_200_OK,
            id="simple-pass",
        ),
        pytest.param(
            "/simple-test",
            {},
            status.HTTP_403_FORBIDDEN,
            id="simple-fail-missing-auth",
        ),
        pytest.param(
            "/and-test",
            {"authorization": "Bearer token", "role": "admin"},
            status.HTTP_200_OK,
            id="and-test-pass",
        ),
        pytest.param(
            "/and-test",
            {"authorization": "Bearer token", "role": "user"},
            status.HTTP_403_FORBIDDEN,
            id="and-test-fail-wrong-role",
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
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            id="and-test-fail-missing-both",
        ),
        pytest.param(
            "/or-test",
            {"authorization": "Bearer token"},
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            id="or-test-fail-missing-role-header",
        ),
        pytest.param(
            "/or-test",
            {"role": "admin"},
            status.HTTP_200_OK,
            id="or-test-pass-role-only",
        ),
        pytest.param(
            "/or-test",
            {"authorization": "Bearer token", "role": "admin"},
            status.HTTP_200_OK,
            id="or-test-pass-both",
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
            id="not-test-pass-no-auth",
        ),
        pytest.param(
            "/not-test",
            {"authorization": "Bearer token"},
            status.HTTP_403_FORBIDDEN,
            id="not-test-fail-has-auth",
        ),
        pytest.param(
            "/complex-test",
            {"authorization": "Bearer token", "role": "admin"},
            status.HTTP_200_OK,
            id="complex-pass-auth-and-admin",
        ),
        pytest.param(
            "/complex-test",
            {},
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            id="complex-fail-missing-role-header",
        ),
        pytest.param(
            "/complex-test",
            {"authorization": "Bearer token", "role": "user"},
            status.HTTP_403_FORBIDDEN,
            id="complex-fail-auth-wrong-role",
        ),
    ],
)
def test_permissions(endpoint, headers, expected_status, app_client) -> None:
    response = app_client.get(endpoint, headers=headers)
    assert response.status_code == expected_status


def test_permission_is_permission_subclass() -> None:
    assert isinstance(has_authorization, Permission)
    assert isinstance(has_admin_role, Permission)


def test_func_permission_stores_func() -> None:
    assert isinstance(has_authorization, FuncPermission)
    assert has_authorization.func is has_authorization_header

    assert isinstance(has_admin_role, FuncPermission)
    assert has_admin_role.func is has_role

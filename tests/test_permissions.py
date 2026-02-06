from collections.abc import Iterator
from dataclasses import dataclass

import pytest
from fastapi import Depends, FastAPI, Request, status
from fastapi.testclient import TestClient

from fastapi_has_permissions import Permission

app = FastAPI()


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

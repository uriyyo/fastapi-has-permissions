from collections.abc import Iterator

import pytest
from fastapi import Depends, FastAPI, Request, status
from fastapi.testclient import TestClient

from fastapi_has_permissions import Permission
from fastapi_has_permissions._results import SkipPermissionCheck

app = FastAPI()


class AlwaysSkip(Permission):
    async def check_permissions(self) -> bool:
        raise SkipPermissionCheck(reason="always skip")


class HasAuthorizationHeader(Permission):
    async def check_permissions(self, request: Request) -> bool:
        return "Authorization" in request.headers


class SkipIfNoToken(Permission):
    """Skips if no Authorization header, otherwise checks if token is valid."""

    async def check_permissions(self, request: Request) -> bool:
        if "Authorization" not in request.headers:
            raise SkipPermissionCheck(reason="no token provided")

        return request.headers["Authorization"] == "valid-token"


class HasRole(Permission):
    async def check_permissions(self, request: Request) -> bool:
        return request.headers.get("role") == "admin"


@app.get(
    "/simple-skip",
    dependencies=[
        Depends(AlwaysSkip()),
    ],
)
@app.get(
    "/skip-if-no-token",
    dependencies=[
        Depends(SkipIfNoToken()),
    ],
)
@app.get(
    "/and-skip-and-pass",
    dependencies=[
        Depends(AlwaysSkip() & HasAuthorizationHeader()),
    ],
)
@app.get(
    "/and-skip-and-fail",
    dependencies=[
        Depends(AlwaysSkip() & HasRole()),
    ],
)
@app.get(
    "/and-all-skip",
    dependencies=[
        Depends(AlwaysSkip() & AlwaysSkip()),
    ],
)
@app.get(
    "/or-skip-and-pass",
    dependencies=[
        Depends(AlwaysSkip() | HasAuthorizationHeader()),
    ],
)
@app.get(
    "/or-skip-and-fail",
    dependencies=[
        Depends(AlwaysSkip() | HasRole()),
    ],
)
@app.get(
    "/or-all-skip",
    dependencies=[
        Depends(AlwaysSkip() | AlwaysSkip()),
    ],
)
@app.get(
    "/not-skip",
    dependencies=[
        Depends(~AlwaysSkip()),
    ],
)
@app.get(
    "/complex-skip",
    dependencies=[
        Depends((SkipIfNoToken() & HasRole()) | HasAuthorizationHeader()),
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
            "/simple-skip",
            {},
            status.HTTP_200_OK,
            id="simple-skip-always-skipped",
        ),
        pytest.param(
            "/skip-if-no-token",
            {},
            status.HTTP_200_OK,
            id="skip-if-no-token-missing-header-skips",
        ),
        pytest.param(
            "/skip-if-no-token",
            {"Authorization": "valid-token"},
            status.HTTP_200_OK,
            id="skip-if-no-token-valid-token-passes",
        ),
        pytest.param(
            "/skip-if-no-token",
            {"Authorization": "invalid-token"},
            status.HTTP_403_FORBIDDEN,
            id="skip-if-no-token-invalid-token-fails",
        ),
        pytest.param(
            "/and-skip-and-pass",
            {"Authorization": "some-token"},
            status.HTTP_200_OK,
            id="and-skip-and-pass-auth-present",
        ),
        pytest.param(
            "/and-skip-and-fail",
            {},
            status.HTTP_403_FORBIDDEN,
            id="and-skip-and-fail-no-role",
        ),
        pytest.param(
            "/and-skip-and-fail",
            {"role": "admin"},
            status.HTTP_200_OK,
            id="and-skip-and-fail-has-admin-role",
        ),
        pytest.param(
            "/and-skip-and-fail",
            {"role": "user"},
            status.HTTP_403_FORBIDDEN,
            id="and-skip-and-fail-wrong-role",
        ),
        pytest.param(
            "/and-all-skip",
            {},
            status.HTTP_200_OK,
            id="and-all-skip-both-skipped",
        ),
        pytest.param(
            "/or-skip-and-pass",
            {"Authorization": "some-token"},
            status.HTTP_200_OK,
            id="or-skip-and-pass-auth-present",
        ),
        pytest.param(
            "/or-skip-and-fail",
            {},
            status.HTTP_200_OK,
            id="or-skip-and-fail-no-role-skipped",
        ),
        pytest.param(
            "/or-skip-and-fail",
            {"role": "user"},
            status.HTTP_200_OK,
            id="or-skip-and-fail-wrong-role-skipped",
        ),
        pytest.param(
            "/or-all-skip",
            {},
            status.HTTP_200_OK,
            id="or-all-skip-both-skipped",
        ),
        pytest.param(
            "/not-skip",
            {},
            status.HTTP_200_OK,
            id="not-skip-passthrough",
        ),
        pytest.param(
            "/complex-skip",
            {},
            status.HTTP_403_FORBIDDEN,
            id="complex-skip-no-headers",
        ),
        pytest.param(
            "/complex-skip",
            {"Authorization": "valid-token"},
            status.HTTP_200_OK,
            id="complex-skip-valid-token-no-role",
        ),
        pytest.param(
            "/complex-skip",
            {"Authorization": "valid-token", "role": "admin"},
            status.HTTP_200_OK,
            id="complex-skip-valid-token-and-admin-role",
        ),
        pytest.param(
            "/complex-skip",
            {"Authorization": "invalid-token", "role": "admin"},
            status.HTTP_200_OK,
            id="complex-skip-invalid-token-but-has-auth-header",
        ),
        pytest.param(
            "/complex-skip",
            {"role": "admin"},
            status.HTTP_200_OK,
            id="complex-skip-admin-role-no-auth-skips-token-check",
        ),
    ],
)
def test_permissions(endpoint, headers, expected_status, app_client) -> None:
    response = app_client.get(endpoint, headers=headers)
    assert response.status_code == expected_status

from collections.abc import Iterator
from typing import Annotated

import pytest
from fastapi import Depends, FastAPI, Header, status
from fastapi.testclient import TestClient

import fastapi_has_permissions as root
from fastapi_has_permissions import add_permissions, common
from fastapi_has_permissions.common import HasRole, HasScope, IsAuthenticated


async def get_is_authenticated(authorization: Annotated[str | None, Header()] = None) -> bool:
    return authorization is not None


async def get_scopes(x_scopes: Annotated[str | None, Header()] = None) -> list[str]:
    if x_scopes is None:
        return []

    return x_scopes.split(",")


async def get_role(x_role: Annotated[str | None, Header()] = None) -> str:
    return x_role or ""


app = FastAPI()
add_permissions(app)


@app.get(
    "/is-authenticated",
    dependencies=[
        Depends(
            IsAuthenticated(
                Depends(get_is_authenticated),
            ),
        ),
    ],
)
async def route() -> str:
    return "You have access to this endpoint!"


@app.get(
    "/has-scope-read",
    dependencies=[
        Depends(
            HasScope(
                Depends(get_scopes),
                scopes=["read"],
            ),
        ),
    ],
)
async def route_has_scope_read() -> str:
    return "You have access to this endpoint!"


@app.get(
    "/has-scope-read-write",
    dependencies=[
        Depends(
            HasScope(
                Depends(get_scopes),
                scopes=["read", "write"],
            ),
        ),
    ],
)
async def route_has_scope_read_write() -> str:
    return "You have access to this endpoint!"


@app.get(
    "/has-role-admin",
    dependencies=[
        Depends(
            HasRole(
                Depends(get_role),
                roles=["admin"],
            ),
        ),
    ],
)
async def route_has_role_admin() -> str:
    return "You have access to this endpoint!"


@app.get(
    "/has-role-admin-or-moderator",
    dependencies=[
        Depends(
            HasRole(
                Depends(get_role),
                roles=["admin", "moderator"],
            ),
        ),
    ],
)
async def route_has_role_admin_or_moderator() -> str:
    return "You have access to this endpoint!"


@app.get(
    "/authenticated-and-admin",
    dependencies=[
        Depends(
            IsAuthenticated(Depends(get_is_authenticated)) & HasRole(Depends(get_role), roles=["admin"]),
        ),
    ],
)
async def route_authenticated_and_admin() -> str:
    return "You have access to this endpoint!"


@app.get(
    "/admin-or-moderator-role",
    dependencies=[
        Depends(
            HasRole(Depends(get_role), roles=["admin"]) | HasRole(Depends(get_role), roles=["moderator"]),
        ),
    ],
)
async def route_admin_or_moderator_role() -> str:
    return "You have access to this endpoint!"


@app.get(
    "/has-role-from-generator",
    dependencies=[
        Depends(
            HasRole(
                Depends(get_role),
                roles=(role for role in ["admin"]),
            ),
        ),
    ],
)
async def route_has_role_from_generator() -> str:
    return "You have access to this endpoint!"


@app.get(
    "/has-role-from-str",
    dependencies=[
        Depends(
            HasRole(
                Depends(get_role),
                roles="admin",
            ),
        ),
    ],
)
async def route_has_role_from_str() -> str:
    return "You have access to this endpoint!"


@app.get(
    "/not-admin",
    dependencies=[
        Depends(
            ~HasRole(Depends(get_role), roles=["admin"]),
        ),
    ],
)
async def route_not_admin() -> str:
    return "You have access to this endpoint!"


@pytest.fixture(scope="session")
def app_client() -> Iterator[TestClient]:
    with TestClient(app) as client:
        yield client


@pytest.mark.parametrize(
    ("endpoint", "headers", "expected_status"),
    [
        pytest.param(
            "/is-authenticated",
            {"Authorization": "Bearer token"},
            status.HTTP_200_OK,
            id="is-authenticated-pass",
        ),
        # authentication failures are 401, not 403
        pytest.param(
            "/is-authenticated",
            {},
            status.HTTP_401_UNAUTHORIZED,
            id="is-authenticated-fail-no-header",
        ),
        pytest.param(
            "/has-scope-read",
            {"x-scopes": "read"},
            status.HTTP_200_OK,
            id="has-scope-read-pass",
        ),
        pytest.param(
            "/has-scope-read",
            {"x-scopes": "write"},
            status.HTTP_403_FORBIDDEN,
            id="has-scope-read-fail-wrong-scope",
        ),
        pytest.param(
            "/has-scope-read",
            {},
            status.HTTP_403_FORBIDDEN,
            id="has-scope-read-fail-no-scopes",
        ),
        pytest.param(
            "/has-scope-read",
            {"x-scopes": "read,write"},
            status.HTTP_200_OK,
            id="has-scope-read-pass-multiple-scopes-including-read",
        ),
        pytest.param(
            "/has-scope-read-write",
            {"x-scopes": "read,write"},
            status.HTTP_200_OK,
            id="has-scope-read-write-pass-both",
        ),
        pytest.param(
            "/has-scope-read-write",
            {"x-scopes": "read"},
            status.HTTP_403_FORBIDDEN,
            id="has-scope-read-write-fail-missing-write",
        ),
        pytest.param(
            "/has-scope-read-write",
            {"x-scopes": "write"},
            status.HTTP_403_FORBIDDEN,
            id="has-scope-read-write-fail-missing-read",
        ),
        pytest.param(
            "/has-scope-read-write",
            {},
            status.HTTP_403_FORBIDDEN,
            id="has-scope-read-write-fail-no-scopes",
        ),
        pytest.param(
            "/has-scope-read-write",
            {"x-scopes": "read,write,delete"},
            status.HTTP_200_OK,
            id="has-scope-read-write-pass-superset-of-required",
        ),
        # HasRole - single role
        pytest.param(
            "/has-role-admin",
            {"x-role": "admin"},
            status.HTTP_200_OK,
            id="has-role-admin-pass",
        ),
        pytest.param(
            "/has-role-admin",
            {"x-role": "user"},
            status.HTTP_403_FORBIDDEN,
            id="has-role-admin-fail-wrong-role",
        ),
        pytest.param(
            "/has-role-admin",
            {},
            status.HTTP_403_FORBIDDEN,
            id="has-role-admin-fail-no-role",
        ),
        pytest.param(
            "/has-role-admin-or-moderator",
            {"x-role": "admin"},
            status.HTTP_200_OK,
            id="has-role-admin-or-moderator-pass-admin",
        ),
        pytest.param(
            "/has-role-admin-or-moderator",
            {"x-role": "moderator"},
            status.HTTP_200_OK,
            id="has-role-admin-or-moderator-pass-moderator",
        ),
        pytest.param(
            "/has-role-admin-or-moderator",
            {"x-role": "user"},
            status.HTTP_403_FORBIDDEN,
            id="has-role-admin-or-moderator-fail-wrong-role",
        ),
        pytest.param(
            "/has-role-admin-or-moderator",
            {},
            status.HTTP_403_FORBIDDEN,
            id="has-role-admin-or-moderator-fail-no-role",
        ),
        pytest.param(
            "/authenticated-and-admin",
            {"Authorization": "Bearer token", "x-role": "admin"},
            status.HTTP_200_OK,
            id="authenticated-and-admin-pass",
        ),
        pytest.param(
            "/authenticated-and-admin",
            {"Authorization": "Bearer token", "x-role": "user"},
            status.HTTP_403_FORBIDDEN,
            id="authenticated-and-admin-fail-wrong-role",
        ),
        pytest.param(
            "/authenticated-and-admin",
            {"x-role": "admin"},
            status.HTTP_401_UNAUTHORIZED,
            id="authenticated-and-admin-fail-not-authenticated",
        ),
        pytest.param(
            "/authenticated-and-admin",
            {},
            status.HTTP_401_UNAUTHORIZED,
            id="authenticated-and-admin-fail-neither",
        ),
        pytest.param(
            "/admin-or-moderator-role",
            {"x-role": "admin"},
            status.HTTP_200_OK,
            id="admin-or-moderator-pass-admin",
        ),
        pytest.param(
            "/admin-or-moderator-role",
            {"x-role": "moderator"},
            status.HTTP_200_OK,
            id="admin-or-moderator-pass-moderator",
        ),
        pytest.param(
            "/admin-or-moderator-role",
            {"x-role": "user"},
            status.HTTP_403_FORBIDDEN,
            id="admin-or-moderator-fail-wrong-role",
        ),
        pytest.param(
            "/admin-or-moderator-role",
            {},
            status.HTTP_403_FORBIDDEN,
            id="admin-or-moderator-fail-no-role",
        ),
        # roles/scopes are normalized to frozensets, so one-shot iterables keep working
        pytest.param(
            "/has-role-from-generator",
            {"x-role": "admin"},
            status.HTTP_200_OK,
            id="has-role-generator-first-request",
        ),
        pytest.param(
            "/has-role-from-generator",
            {"x-role": "admin"},
            status.HTTP_200_OK,
            id="has-role-generator-second-request-not-consumed",
        ),
        # a plain string is a single role, not an iterable of characters
        pytest.param(
            "/has-role-from-str",
            {"x-role": "admin"},
            status.HTTP_200_OK,
            id="has-role-str-pass",
        ),
        pytest.param(
            "/has-role-from-str",
            {"x-role": "a"},
            status.HTTP_403_FORBIDDEN,
            id="has-role-str-not-treated-as-chars",
        ),
        pytest.param(
            "/not-admin",
            {"x-role": "user"},
            status.HTTP_200_OK,
            id="not-admin-pass-non-admin-role",
        ),
        pytest.param(
            "/not-admin",
            {},
            status.HTTP_200_OK,
            id="not-admin-pass-no-role",
        ),
        pytest.param(
            "/not-admin",
            {"x-role": "admin"},
            status.HTTP_403_FORBIDDEN,
            id="not-admin-fail-is-admin",
        ),
    ],
)
def test_permissions(endpoint, headers, expected_status, app_client) -> None:
    response = app_client.get(endpoint, headers=headers)
    assert response.status_code == expected_status


def test_common_is_re_exported_from_the_root() -> None:
    for name in common.__all__:
        assert getattr(root, name, None) is getattr(common, name), name
        assert name in root.__all__, name

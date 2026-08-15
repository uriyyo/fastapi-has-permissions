from collections.abc import Iterator
from typing import Annotated, ClassVar

import pytest
from fastapi import Depends, FastAPI, Header, Request, status
from fastapi.testclient import TestClient

from fastapi_has_permissions import Permission, WithError, add_permissions, evaluate, permission
from fastapi_has_permissions.common import IsAuthenticated


async def get_is_authenticated(authorization: Annotated[str | None, Header()] = None) -> bool:
    return authorization is not None


class HasAuthorizationHeader(Permission):
    default_exc_code: ClassVar[str] = "missing_authorization"

    async def check_permissions(self, request: Request) -> bool:
        return "Authorization" in request.headers


@permission(code="not_admin", message="Admin role required")
async def has_admin_role(role: Annotated[str | None, Header()] = None) -> bool:
    return role == "admin"


app = FastAPI()
add_permissions(app)


@app.get(
    "/coded-error",
    dependencies=[Depends(HasAuthorizationHeader())],
)
@app.get(
    "/coded-func-error",
    dependencies=[Depends(has_admin_role())],
)
@app.get(
    "/coded-error-composed",
    dependencies=[Depends(HasAuthorizationHeader() & has_admin_role())],
)
@app.get(
    "/coded-error-or-composed",
    dependencies=[Depends(HasAuthorizationHeader() | has_admin_role())],
)
@app.get(
    "/authenticated",
    dependencies=[Depends(IsAuthenticated(Depends(get_is_authenticated)))],
)
async def route() -> str:
    return "You have access to this endpoint!"


@pytest.fixture(scope="session")
def app_client() -> Iterator[TestClient]:
    with TestClient(app) as client:
        yield client


def test_coded_error_body(app_client) -> None:
    response = app_client.get("/coded-error")

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json()["detail"] == {
        "code": "missing_authorization",
        "message": "Permission denied",
    }


def test_plain_error_body_unchanged_without_code(app_client) -> None:
    response = app_client.get("/authenticated", headers={"Authorization": "token"})

    assert response.status_code == status.HTTP_200_OK


def test_coded_func_error_body(app_client) -> None:
    response = app_client.get("/coded-func-error")

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json()["detail"] == {
        "code": "not_admin",
        "message": "Admin role required",
    }


def test_code_propagates_through_composition(app_client) -> None:
    response = app_client.get("/coded-error-composed", headers={"role": "admin"})

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json()["detail"] == {
        "code": "missing_authorization",
        "message": "Permission denied",
    }


def test_unauthenticated_is_401_with_challenge(app_client) -> None:
    response = app_client.get("/authenticated")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert response.json()["detail"] == "Not authenticated"


def test_code_survives_multi_branch_aggregation(app_client) -> None:
    response = app_client.get("/coded-error-or-composed")

    # both branches fail: reasons are joined, and the first failure supplies the code
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json()["detail"] == {
        "code": "missing_authorization",
        "message": "Permission denied; Admin role required",
    }


class DynamicMessage(Permission):
    role: str

    def get_exc_message(self) -> str:
        return f"You need the {self.role!r} role"

    async def check_permissions(self) -> bool:
        return False


@pytest.mark.asyncio
async def test_overridden_get_exc_message_is_used() -> None:
    assert (await evaluate(DynamicMessage("admin"))).reason == "You need the 'admin' role"
    assert (await evaluate(WithError(DynamicMessage("admin")))).reason == "You need the 'admin' role"
    assert (await evaluate(WithError(DynamicMessage("admin"), message="Not found"))).reason == "Not found"

from collections.abc import Iterator
from typing import Annotated

import pytest
from fastapi import Depends, FastAPI, Header, status
from fastapi.testclient import TestClient
from fastapi_injected import push_overrides

from fastapi_has_permissions import Evaluate, Permission, add_permissions, evaluate, is_failed, is_successful


async def get_role(x_role: Annotated[str | None, Header()] = None) -> str:
    return x_role or ""


class HasAdminRole(Permission):
    async def check_permissions(self, role: Annotated[str, Depends(get_role)]) -> bool:
        return role == "admin"


app = FastAPI()
add_permissions(app)


@app.get("/imperative-check")
async def imperative_check(evaluator: Evaluate) -> dict[str, bool]:
    return {"is_admin": await evaluator.check(HasAdminRole())}


@app.get("/imperative-require")
async def imperative_require(evaluator: Evaluate) -> str:
    await evaluator.require(HasAdminRole())
    return "You have access to this endpoint!"


@pytest.fixture(scope="session")
def app_client() -> Iterator[TestClient]:
    with TestClient(app) as client:
        yield client


def test_evaluator_check_pass(app_client) -> None:
    response = app_client.get("/imperative-check", headers={"x-role": "admin"})

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"is_admin": True}


def test_evaluator_check_fail_without_raising(app_client) -> None:
    response = app_client.get("/imperative-check", headers={"x-role": "user"})

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"is_admin": False}


def test_evaluator_require_pass(app_client) -> None:
    response = app_client.get("/imperative-require", headers={"x-role": "admin"})

    assert response.status_code == status.HTTP_200_OK


def test_evaluator_require_raises(app_client) -> None:
    response = app_client.get("/imperative-require", headers={"x-role": "user"})

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json()["detail"] == "Permission denied"


@pytest.mark.asyncio
async def test_evaluate_standalone_with_overrides() -> None:
    with push_overrides({get_role: "admin"}):
        assert is_successful(await evaluate(HasAdminRole()))

    with push_overrides({get_role: "user"}):
        assert is_failed(await evaluate(HasAdminRole()))

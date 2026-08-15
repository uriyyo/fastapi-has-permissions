from collections.abc import Iterator
from typing import Annotated

import pytest
from fastapi import Depends, FastAPI, status
from fastapi.testclient import TestClient

from fastapi_has_permissions import Permission, add_permissions

calls: list[str] = []


async def counting_dep() -> bool:
    calls.append("counting_dep")
    return True


class AlwaysPass(Permission):
    async def check_permissions(self) -> bool:
        return True


class AlwaysFail(Permission):
    async def check_permissions(self) -> bool:
        return False


class ExpensivePermission(Permission):
    async def check_permissions(self, value: Annotated[bool, Depends(counting_dep)]) -> bool:
        return value


app = FastAPI()
add_permissions(app)


@app.get(
    "/or-short-circuits",
    dependencies=[
        Depends(AlwaysPass() | ExpensivePermission()),
    ],
)
@app.get(
    "/or-reaches-second-branch",
    dependencies=[
        Depends(AlwaysFail() | ExpensivePermission()),
    ],
)
async def route() -> str:
    return "You have access to this endpoint!"


@pytest.fixture(scope="session")
def app_client() -> Iterator[TestClient]:
    with TestClient(app) as client:
        yield client


def test_or_never_resolves_losing_branch(app_client) -> None:
    calls.clear()

    response = app_client.get("/or-short-circuits")

    assert response.status_code == status.HTTP_200_OK
    assert calls == []


def test_or_resolves_branch_when_needed(app_client) -> None:
    calls.clear()

    response = app_client.get("/or-reaches-second-branch")

    assert response.status_code == status.HTTP_200_OK
    assert calls == ["counting_dep"]

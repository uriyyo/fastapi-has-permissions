from collections.abc import Iterator
from typing import Annotated

import pytest
from fastapi import Depends, FastAPI, Header
from fastapi.testclient import TestClient

from fastapi_has_permissions import Dep, DepFactory, Permission, lazy, permission


async def get_role(role: Annotated[str, Header()]) -> str:
    return role


RoleDep = DepFactory[str, get_role]


class HasRole(Permission):
    role_dep: Dep[str]
    expected: str

    async def check_permissions(self, role: str, /) -> bool:
        return role == self.expected


@permission
async def role_is(role_dep: Dep[str], /, expected: Annotated[str, Header()]) -> bool:
    return role_dep == expected


app = FastAPI()


@app.get("/class-based", dependencies=[Depends(HasRole(RoleDep, "admin"))])
async def class_based() -> str:
    return "ok"


@app.get("/lazy", dependencies=[Depends(lazy(HasRole(RoleDep, "admin")))])
async def lazy_based() -> str:
    return "ok"


@app.get("/function-based", dependencies=[Depends(role_is(RoleDep))])
async def function_based() -> str:
    return "ok"


@pytest.fixture(scope="session")
def app_client() -> Iterator[TestClient]:
    with TestClient(app) as client:
        yield client


@pytest.mark.parametrize("endpoint", ["/class-based", "/lazy", "/function-based"])
@pytest.mark.parametrize(
    ("role", "expected_status"),
    [
        pytest.param("admin", 200, id="allowed"),
        pytest.param("user", 403, id="denied"),
    ],
)
def test_dep_factory_fills_dep_slot(endpoint, role, expected_status, app_client) -> None:
    response = app_client.get(endpoint, headers={"role": role, "expected": "admin"})

    assert response.status_code == expected_status


def test_dep_factory_is_annotated_depends() -> None:
    assert RoleDep == Annotated[str, Depends(get_role)]

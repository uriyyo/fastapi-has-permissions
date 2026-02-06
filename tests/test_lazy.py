from collections.abc import Iterator
from dataclasses import dataclass
from typing import Annotated

import pytest
from fastapi import Depends, FastAPI, Header
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient

from fastapi_has_permissions import Permission, lazy

app = FastAPI()


@dataclass
class AgeIsMoreThan(Permission):
    age: int

    async def check_permissions(self, age: Annotated[int, Header()]) -> bool:
        return age > self.age


@app.get(
    "/age-restricted-endpoint",
    dependencies=[
        Depends(lazy(AgeIsMoreThan(age=18), skip_on_exc=(RequestValidationError,))),
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
        pytest.param("/age-restricted-endpoint", {"age": "20"}, 200, id="age-over-18"),
        pytest.param("/age-restricted-endpoint", {"age": "17"}, 403, id="age-under-18"),
        pytest.param("/age-restricted-endpoint", {"age": "invalid"}, 200, id="invalid-age"),
        pytest.param("/age-restricted-endpoint", {}, 200, id="missing-age"),
    ],
)
def test_permissions(endpoint, headers, expected_status, app_client) -> None:
    response = app_client.get(endpoint, headers=headers)
    assert response.status_code == expected_status

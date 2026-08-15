from collections.abc import Iterator
from dataclasses import dataclass
from typing import Annotated

import pytest
from fastapi import Depends, FastAPI, Header, Path
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient

from fastapi_has_permissions import Permission, add_permissions, lazy

app = FastAPI()
add_permissions(app)


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


async def is_staff() -> bool:
    return False


class IsArticleAuthor(Permission):
    async def check_permissions(
        self,
        article_id: Annotated[int, Path()],
        staff: Annotated[bool, Depends(is_staff)],
    ) -> bool:
        return article_id == 1 or staff


lazy_app = FastAPI()
add_permissions(lazy_app)


@lazy_app.get("/articles/{article_id}", dependencies=[Depends(lazy(IsArticleAuthor()))])
async def article(article_id: int) -> str:
    return f"You have access to article {article_id}!"


@pytest.fixture
def lazy_client() -> Iterator[TestClient]:
    with TestClient(lazy_app) as client:
        yield client

    lazy_app.dependency_overrides.clear()


@pytest.mark.parametrize(
    ("endpoint", "expected_status"),
    [
        pytest.param("/articles/1", 200, id="author"),
        pytest.param("/articles/2", 403, id="not-author"),
    ],
)
def test_lazy_resolves_path_params(endpoint, expected_status, lazy_client) -> None:
    response = lazy_client.get(endpoint)

    assert response.status_code == expected_status


@pytest.mark.parametrize(
    ("staff", "expected_status"),
    [
        pytest.param(True, 200, id="staff"),
        pytest.param(False, 403, id="not-staff"),
    ],
)
def test_lazy_respects_dependency_overrides(staff, expected_status, lazy_client) -> None:
    lazy_app.dependency_overrides[is_staff] = lambda: staff

    response = lazy_client.get("/articles/2")

    assert response.status_code == expected_status


def test_lazy_shares_dependency_cache_with_route() -> None:
    calls = 0

    async def counted() -> int:
        nonlocal calls
        calls += 1
        return calls

    class UsesCounted(Permission):
        async def check_permissions(self, value: Annotated[int, Depends(counted)]) -> bool:
            return value > 0

    cache_app = FastAPI()
    add_permissions(cache_app)

    @cache_app.get("/cached", dependencies=[Depends(lazy(UsesCounted()))])
    async def cached(value: Annotated[int, Depends(counted)]) -> int:
        return value

    with TestClient(cache_app) as client:
        assert client.get("/cached").is_success

    # the route and the lazy permission must share a single resolution per request
    assert calls == 1


async def raises_value_error() -> str:
    raise ValueError("boom")


class UsesFailingDep(Permission):
    async def check_permissions(self, value: Annotated[str, Depends(raises_value_error)]) -> bool:
        return bool(value)


error_app = FastAPI()
add_permissions(error_app)


@error_app.get(
    "/error",
    dependencies=[Depends(lazy(UsesFailingDep(), skip_on_exc=(RequestValidationError,)))],
)
async def error_route() -> str:
    return "You have access to this endpoint!"


def test_lazy_does_not_swallow_unrelated_value_errors() -> None:
    # a ValueError raised by a dependency must not be mistaken for a validation
    # error and silently turned into a skipped check
    with TestClient(error_app, raise_server_exceptions=True) as client, pytest.raises(ValueError, match="boom"):
        client.get("/error")

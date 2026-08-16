from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass
from typing import Annotated

import pytest
from fastapi import Depends, FastAPI, Header, Path, status
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient

from fastapi_has_permissions import AllowSkipped, Permission, SkipOnExc, add_permissions, evaluate
from fastapi_has_permissions.common import Allow

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
        Depends(AllowSkipped(SkipOnExc(AgeIsMoreThan(age=18), (RequestValidationError,)))),
    ],
)
@app.get(
    "/strict-age-restricted-endpoint",
    dependencies=[
        Depends(SkipOnExc(AgeIsMoreThan(age=18), (RequestValidationError,))),
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
        pytest.param("/strict-age-restricted-endpoint", {"age": "20"}, 200, id="strict-age-over-18"),
        pytest.param("/strict-age-restricted-endpoint", {"age": "invalid"}, 403, id="strict-invalid-age"),
        pytest.param("/strict-age-restricted-endpoint", {}, 403, id="strict-missing-age"),
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


article_app = FastAPI()
add_permissions(article_app)


@article_app.get("/articles/{article_id}", dependencies=[Depends(IsArticleAuthor())])
async def article(article_id: int) -> str:
    return f"You have access to article {article_id}!"


@pytest.fixture
def article_client() -> Iterator[TestClient]:
    with TestClient(article_app) as client:
        yield client

    article_app.dependency_overrides.clear()


@pytest.mark.parametrize(
    ("endpoint", "expected_status"),
    [
        pytest.param("/articles/1", 200, id="author"),
        pytest.param("/articles/2", 403, id="not-author"),
    ],
)
def test_path_params_are_resolved(endpoint, expected_status, article_client) -> None:
    response = article_client.get(endpoint)

    assert response.status_code == expected_status


@pytest.mark.parametrize(
    ("staff", "expected_status"),
    [
        pytest.param(True, 200, id="staff"),
        pytest.param(False, 403, id="not-staff"),
    ],
)
def test_dependency_overrides_are_respected(staff, expected_status, article_client) -> None:
    article_app.dependency_overrides[is_staff] = lambda: staff

    response = article_client.get("/articles/2")

    assert response.status_code == expected_status


def test_dependency_cache_is_shared_with_the_route() -> None:
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

    @cache_app.get("/cached", dependencies=[Depends(UsesCounted())])
    async def cached(value: Annotated[int, Depends(counted)]) -> int:
        return value

    with TestClient(cache_app) as client:
        assert client.get("/cached").is_success

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
    dependencies=[Depends(SkipOnExc(UsesFailingDep(), (RequestValidationError,)))],
)
async def error_route() -> str:
    return "You have access to this endpoint!"


def test_unrelated_value_errors_are_not_swallowed() -> None:
    with TestClient(error_app, raise_server_exceptions=True) as client, pytest.raises(ValueError, match="boom"):
        client.get("/error")


@pytest.mark.asyncio
async def test_yield_dependencies_stay_open_for_the_check() -> None:
    events: list[str] = []

    async def managed() -> AsyncIterator[str]:
        events.append("open")
        try:
            yield "resource"
        finally:
            events.append("close")

    class UsesManaged(Permission):
        async def check_permissions(self, resource: Annotated[str, Depends(managed)]) -> bool:
            events.append(f"check saw {resource!r}")
            return True

    await evaluate(UsesManaged())

    assert events == ["open", "check saw 'resource'", "close"]


class TestNestedDeferral:
    @pytest.fixture
    def nested_client(self) -> Iterator[TestClient]:
        nested_app = FastAPI()
        add_permissions(nested_app)

        guarded = SkipOnExc(UsesFailingDep(), (ValueError,))

        @nested_app.get("/nested", dependencies=[Depends(AllowSkipped(guarded & Allow()))])
        async def nested() -> str:
            return "ok"

        with TestClient(nested_app, raise_server_exceptions=True) as client:
            yield client

    def test_exceptions_from_a_nested_dependency_are_caught(self, nested_client: TestClient) -> None:
        assert nested_client.get("/nested").status_code == status.HTTP_200_OK

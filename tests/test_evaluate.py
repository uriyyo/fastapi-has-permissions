from collections.abc import Iterator
from typing import Annotated

import pytest
from fastapi import Depends, FastAPI, Header, Request, status
from fastapi.testclient import TestClient
from fastapi_injected import push_overrides

from fastapi_has_permissions import (
    AllowSkipped,
    CheckResult,
    Dep,
    Eval,
    Evaluate,
    Given,
    Permission,
    PermissionDeniedError,
    PermissionEvaluator,
    add_permissions,
    evaluate,
    is_failed,
    is_skipped,
    is_successful,
    skip,
)


async def get_role(x_role: Annotated[str | None, Header()] = None) -> str:
    return x_role or ""


repo_calls = 0


async def get_repo() -> str:
    global repo_calls  # noqa: PLW0603
    repo_calls += 1
    return "repo"


class IsEven(Permission):
    value: Dep[int]

    async def check_permissions(self, value: int, /) -> bool:
        return value % 2 == 0


class HasAdminRole(Permission):
    async def check_permissions(self, role: Annotated[str, Depends(get_role)]) -> bool:
        return role == "admin"


class AlwaysSkip(Permission):
    async def check_permissions(self) -> bool:
        skip("always skip")


app = FastAPI()
add_permissions(app)


@app.get("/eval")
async def eval_route(result: Eval[CheckResult, HasAdminRole()]) -> dict[str, bool]:
    return {"is_admin": is_successful(result)}


@app.get("/guard", dependencies=[Depends(HasAdminRole())])
async def guard_route() -> str:
    return "You have access to this endpoint!"


@app.get("/imperative-check")
async def imperative_check(evaluator: Evaluate) -> dict[str, bool]:
    return {"is_admin": await evaluator.check(HasAdminRole())}


@app.get("/imperative-require")
async def imperative_require(evaluator: Evaluate) -> str:
    await evaluator.require(HasAdminRole())
    return "You have access to this endpoint!"


@app.get("/imperative-require-skipping")
async def imperative_require_skipping(evaluator: Evaluate) -> str:
    await evaluator.require(AlwaysSkip())
    return "You have access to this endpoint!"


@app.get("/imperative-require-allow-skipped")
async def imperative_require_allow_skipped(evaluator: Evaluate) -> str:
    await evaluator.require(AllowSkipped(AlwaysSkip()))
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


def test_evaluator_require_raises_on_skip(app_client) -> None:
    response = app_client.get("/imperative-require-skipping")

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json()["detail"] == "Permission denied"


def test_evaluator_require_allows_explicitly_allowed_skip(app_client) -> None:
    response = app_client.get("/imperative-require-allow-skipped")

    assert response.status_code == status.HTTP_200_OK


@pytest.mark.asyncio
async def test_evaluate_returns_skipped_without_raising() -> None:
    assert is_skipped(await evaluate(AlwaysSkip()))


@pytest.mark.asyncio
async def test_evaluate_standalone_with_overrides() -> None:
    with push_overrides({get_role: "admin"}):
        assert is_successful(await evaluate(HasAdminRole()))

    with push_overrides({get_role: "user"}):
        assert is_failed(await evaluate(HasAdminRole()))


@pytest.mark.parametrize(
    ("headers", "expected"),
    [
        pytest.param({"x-role": "admin"}, True, id="allowed"),
        pytest.param({}, False, id="denied"),
    ],
)
def test_eval_returns_the_result_instead_of_raising(headers, expected, app_client) -> None:
    response = app_client.get("/eval", headers=headers)

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"is_admin": expected}


def test_a_permission_used_as_a_guard_always_raises(app_client) -> None:
    # a permission reached as a dependency is an enforcement point - there is no
    # opt-out, `Eval` is how a caller asks for the result instead
    assert app_client.get("/guard").status_code == status.HTTP_403_FORBIDDEN
    assert app_client.get("/guard", headers={"x-role": "admin"}).status_code == status.HTTP_200_OK


def test_eval_rejects_a_malformed_subscript() -> None:
    with pytest.raises(TypeError):
        Eval[CheckResult]

    with pytest.raises(TypeError):
        Eval[CheckResult, "not a permission"]


def test_eval_is_value_equal() -> None:
    assert Eval[CheckResult, HasAdminRole()] == Eval[CheckResult, HasAdminRole()]
    assert Eval[CheckResult, HasAdminRole()] != Eval[CheckResult, AlwaysSkip()]


class UsesRepo(Permission):
    async def check_permissions(self, repo: Annotated[str, Depends(get_repo)]) -> bool:
        return repo == "repo"


class ReadsRequest(Permission):
    async def check_permissions(self, request: Request) -> bool:
        return request.headers.get("x-token") == "secret"


class ToolError(Exception):
    pass


@app.get("/inherits-request")
async def inherits_request() -> dict[str, bool]:
    async with evaluate.scope({get_role: "admin"}) as perms:
        return {
            "reads_request": await perms.check(ReadsRequest()),
            "role_bound": await perms.check(HasAdminRole()),
        }


@pytest.mark.asyncio
async def test_module_level_evaluator_has_the_same_api() -> None:
    # the same three calls read identically inside and outside a request
    assert isinstance(evaluate, PermissionEvaluator)

    with push_overrides({get_role: "admin"}):
        assert is_successful(await evaluate(HasAdminRole()))
        assert await evaluate.check(HasAdminRole())
        assert is_successful(await evaluate.require(HasAdminRole()))


@pytest.mark.asyncio
async def test_scope_binds_overrides() -> None:
    async with evaluate.scope({get_role: "admin"}) as perms:
        assert await perms.check(HasAdminRole())

    async with evaluate.scope({get_role: "user"}) as perms:
        assert not await perms.check(HasAdminRole())


@pytest.mark.asyncio
async def test_scope_shares_the_dependency_cache() -> None:
    before = repo_calls

    async with evaluate.scope() as perms:
        for _ in range(3):
            assert await perms.check(UsesRepo())

    # without a scope each call would open its own, resolving the repository every time
    assert repo_calls - before == 1


@pytest.mark.asyncio
async def test_scope_reports_failures_through_on_failure() -> None:
    async with evaluate.scope({get_role: "user"}, on_failure=lambda _, failed: ToolError(failed.reason)) as perms:
        with pytest.raises(ToolError):
            await perms.require(HasAdminRole())


@pytest.mark.asyncio
async def test_scope_requires_raises_on_a_skip() -> None:
    async with evaluate.scope() as perms:
        with pytest.raises(PermissionDeniedError):
            await perms.require(AlwaysSkip())


@pytest.mark.asyncio
async def test_filter_keeps_the_allowed_items() -> None:
    async with evaluate.scope() as perms:
        allowed = await perms.filter(range(1, 7), lambda i: IsEven(Given(i)))

    assert allowed == [2, 4, 6]


def test_scope_inherits_the_surrounding_request(app_client) -> None:
    # the override applies, and request-bound dependencies keep resolving against the real request
    assert app_client.get("/inherits-request", headers={"x-token": "secret"}).json() == {
        "reads_request": True,
        "role_bound": True,
    }
    assert app_client.get("/inherits-request").json() == {
        "reads_request": False,
        "role_bound": True,
    }

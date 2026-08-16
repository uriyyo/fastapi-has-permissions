from collections.abc import Iterator
from typing import Annotated

import pytest
from fastapi import Depends, FastAPI, Header, status
from fastapi.testclient import TestClient
from fastapi_injected import push_overrides

from fastapi_has_permissions import (
    AllowSkipped,
    CheckResult,
    Eval,
    Evaluate,
    Permission,
    add_permissions,
    evaluate,
    is_failed,
    is_skipped,
    is_successful,
    skip,
)


async def get_role(x_role: Annotated[str | None, Header()] = None) -> str:
    return x_role or ""


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

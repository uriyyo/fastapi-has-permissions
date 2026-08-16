from collections.abc import Iterator
from typing import Annotated

import pytest
from fastapi import Depends, FastAPI, Header, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient

from fastapi_has_permissions import (
    Advisory,
    AllowSkipped,
    CheckResult,
    DenySkipped,
    FailOnExc,
    Permission,
    SkipOnExc,
    Skipped,
    WithError,
    add_permissions,
    evaluate,
    fail,
    is_failed,
    skip,
)
from fastapi_has_permissions.common import HasScope, IsAuthenticated


class BackendError(Exception):
    pass


class Passes(Permission):
    async def check_permissions(self) -> bool:
        return True


class Denies(Permission):
    async def check_permissions(self) -> bool:
        fail("article 42 does not exist to you")


class AlsoDenies(Permission):
    async def check_permissions(self) -> bool:
        fail("you are not an editor")


class Skips(Permission):
    async def check_permissions(self) -> bool:
        skip("no opinion")


class Explodes(Permission):
    async def check_permissions(self) -> bool:
        raise BackendError("authorization backend is down")


class HasRole(Permission):
    async def check_permissions(self, request: Request) -> bool:
        return request.headers.get("role") == "admin"


class AgeIsMoreThan(Permission):
    age: int

    async def check_permissions(self, age: Annotated[int, Header()]) -> bool:
        if age == 0:
            raise BackendError("authorization backend is down")

        return age > self.age


async def is_authenticated(authorization: Annotated[str | None, Header()] = None) -> bool:
    return authorization is not None


async def current_scopes(x_scopes: Annotated[str, Header()] = "") -> list[str]:
    return x_scopes.split()


app = FastAPI()
add_permissions(app)


@app.get(
    "/fail-on-exc",
    dependencies=[
        Depends(FailOnExc(Explodes(), (BackendError,))),
    ],
)
@app.get(
    "/fail-on-exc-custom-error",
    dependencies=[
        Depends(
            FailOnExc(
                Explodes(),
                (BackendError,),
                message="Authorization backend unavailable",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            ),
        ),
    ],
)
@app.get(
    "/skip-on-exc",
    dependencies=[
        Depends(SkipOnExc(Explodes(), (BackendError,))),
    ],
)
@app.get(
    "/skip-on-exc-allowed",
    dependencies=[
        Depends(AllowSkipped(SkipOnExc(Explodes(), (BackendError,)))),
    ],
)
@app.get(
    "/skip-on-exc-or-role",
    dependencies=[
        Depends(SkipOnExc(Explodes(), (BackendError,)) | HasRole()),
    ],
)
@app.get(
    "/and-skip",
    dependencies=[
        Depends(Skips() & HasRole()),
    ],
)
@app.get(
    "/and-deny-skipped",
    dependencies=[
        Depends(DenySkipped(Skips()) & HasRole()),
    ],
)
@app.get(
    "/deny-skipped-custom-error",
    dependencies=[
        Depends(DenySkipped(Skips(), message="License check unavailable")),
    ],
)
@app.get(
    "/and-advisory",
    dependencies=[
        Depends(Advisory(Denies()) & HasRole()),
    ],
)
@app.get(
    "/advisory-alone",
    dependencies=[
        Depends(Advisory(Denies())),
    ],
)
@app.get(
    "/with-error",
    dependencies=[
        Depends(WithError(Denies(), message="Not found", status_code=status.HTTP_404_NOT_FOUND)),
    ],
)
@app.get(
    "/with-error-no-message",
    dependencies=[
        Depends(WithError(Denies(), status_code=status.HTTP_404_NOT_FOUND)),
    ],
)
@app.get(
    "/with-error-nested",
    dependencies=[
        Depends(WithError(Denies(), status_code=status.HTTP_404_NOT_FOUND) | AlsoDenies()),
    ],
)
@app.get(
    "/skip-and-exc",
    dependencies=[
        Depends(
            AllowSkipped(
                FailOnExc(
                    SkipOnExc(AgeIsMoreThan(age=18), (RequestValidationError,)),
                    (BackendError,),
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                ),
            ),
        ),
    ],
)
@app.get(
    "/authenticated",
    dependencies=[
        Depends(AllowSkipped(IsAuthenticated(Depends(is_authenticated)))),
    ],
)
@app.get(
    "/authenticated-with-error",
    dependencies=[
        Depends(WithError(IsAuthenticated(Depends(is_authenticated)), status_code=status.HTTP_404_NOT_FOUND)),
    ],
)
@app.get(
    "/scoped",
    dependencies=[
        Depends(AllowSkipped(HasScope(Depends(current_scopes), "articles:write"))),
    ],
)
@app.get(
    "/unlisted-exc",
    dependencies=[
        Depends(FailOnExc(Explodes(), (KeyError,))),
    ],
)
async def route() -> str:
    return "You have access to this endpoint!"


@app.get("/no-auto-error")
async def no_auto_error_route(
    result: Annotated[CheckResult, Depends(AllowSkipped(Denies(), auto_error=False))],
) -> dict[str, bool]:
    return {"denied": is_failed(result)}


@pytest.fixture(scope="session")
def app_client() -> Iterator[TestClient]:
    with TestClient(app) as client:
        yield client


@pytest.mark.parametrize(
    ("endpoint", "headers", "expected_status", "expected_detail"),
    [
        pytest.param(
            "/fail-on-exc",
            {},
            status.HTTP_403_FORBIDDEN,
            "Permission denied",
            id="fail-on-exc-denies-without-exposing-the-exception",
        ),
        pytest.param(
            "/fail-on-exc-custom-error",
            {},
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Authorization backend unavailable",
            id="fail-on-exc-uses-own-error-config",
        ),
        pytest.param(
            "/skip-on-exc",
            {},
            status.HTTP_403_FORBIDDEN,
            None,
            id="skip-on-exc-abstains-and-is-denied-at-root",
        ),
        pytest.param(
            "/skip-on-exc-allowed",
            {},
            status.HTTP_200_OK,
            None,
            id="skip-on-exc-abstains-and-is-allowed-explicitly",
        ),
        pytest.param(
            "/skip-on-exc-or-role",
            {"role": "admin"},
            status.HTTP_200_OK,
            None,
            id="skip-on-exc-lets-other-branch-decide",
        ),
        pytest.param(
            "/and-skip",
            {"role": "admin"},
            status.HTTP_200_OK,
            None,
            id="and-skip-abstains",
        ),
        pytest.param(
            "/and-deny-skipped",
            {"role": "admin"},
            status.HTTP_403_FORBIDDEN,
            None,
            id="and-deny-skipped-does-not-abstain",
        ),
        pytest.param(
            "/deny-skipped-custom-error",
            {},
            status.HTTP_403_FORBIDDEN,
            "License check unavailable",
            id="deny-skipped-uses-own-error-config",
        ),
        pytest.param(
            "/and-advisory",
            {"role": "admin"},
            status.HTTP_200_OK,
            None,
            id="advisory-failure-does-not-deny",
        ),
        pytest.param(
            "/and-advisory",
            {},
            status.HTTP_403_FORBIDDEN,
            None,
            id="advisory-failure-leaves-decision-to-others",
        ),
        pytest.param(
            "/advisory-alone",
            {},
            status.HTTP_403_FORBIDDEN,
            None,
            id="advisory-alone-abstains-and-is-denied-at-root",
        ),
        pytest.param(
            "/with-error",
            {},
            status.HTTP_404_NOT_FOUND,
            "Not found",
            id="with-error-masks-child-error",
        ),
        pytest.param(
            "/with-error-no-message",
            {},
            status.HTTP_404_NOT_FOUND,
            "article 42 does not exist to you",
            id="with-error-keeps-child-reason",
        ),
        pytest.param(
            "/with-error-nested",
            {},
            status.HTTP_404_NOT_FOUND,
            None,
            id="with-error-applies-inside-a-composition",
        ),
        pytest.param(
            "/skip-and-exc",
            {"age": "20"},
            status.HTTP_200_OK,
            None,
            id="skip-and-exc-check-passes",
        ),
        pytest.param(
            "/skip-and-exc",
            {"age": "17"},
            status.HTTP_403_FORBIDDEN,
            None,
            id="skip-and-exc-check-denies",
        ),
        pytest.param(
            "/skip-and-exc",
            {"age": "0"},
            status.HTTP_503_SERVICE_UNAVAILABLE,
            None,
            id="skip-and-exc-check-raises",
        ),
        pytest.param(
            "/skip-and-exc",
            {},
            status.HTTP_200_OK,
            None,
            id="skip-and-exc-dependency-cannot-be-resolved",
        ),
        pytest.param(
            "/authenticated",
            {"Authorization": "token"},
            status.HTTP_200_OK,
            None,
            id="authenticated",
        ),
        pytest.param(
            "/scoped",
            {"x-scopes": "articles:write"},
            status.HTTP_200_OK,
            None,
            id="scoped-has-scope",
        ),
        pytest.param(
            "/scoped",
            {"x-scopes": "articles:read"},
            status.HTTP_403_FORBIDDEN,
            None,
            id="scoped-missing-scope",
        ),
    ],
)
def test_wrappers(endpoint, headers, expected_status, expected_detail, app_client) -> None:
    response = app_client.get(endpoint, headers=headers)

    assert response.status_code == expected_status

    if expected_detail is not None:
        assert response.json()["detail"] == expected_detail


@pytest.mark.parametrize(
    ("endpoint", "expected_status"),
    [
        pytest.param("/authenticated", status.HTTP_401_UNAUTHORIZED, id="child-error-config"),
        pytest.param("/authenticated-with-error", status.HTTP_404_NOT_FOUND, id="masked-status-code"),
    ],
)
def test_wrappers_keep_child_error_headers(endpoint, expected_status, app_client) -> None:
    response = app_client.get(endpoint)

    assert response.status_code == expected_status
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_unlisted_exception_is_not_swallowed(app_client) -> None:
    with pytest.raises(BackendError):
        app_client.get("/unlisted-exc")


def test_no_auto_error(app_client) -> None:
    response = app_client.get("/no-auto-error")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"denied": True}


@pytest.mark.asyncio
async def test_advisory_keeps_failure_reason() -> None:
    assert await evaluate(Advisory(Denies())) == Skipped(reason="article 42 does not exist to you")


@pytest.mark.asyncio
async def test_with_error_leaves_non_failed_results_alone() -> None:
    assert await evaluate(WithError(Passes(), status_code=status.HTTP_404_NOT_FOUND)) is True
    assert await evaluate(WithError(Skips(), status_code=status.HTTP_404_NOT_FOUND)) == Skipped(reason="no opinion")


@pytest.mark.asyncio
async def test_with_error_sets_error_code() -> None:
    result = await evaluate(WithError(Denies(), code="not_found", status_code=status.HTTP_404_NOT_FOUND))

    assert result.code == "not_found"
    assert result.status_code == status.HTTP_404_NOT_FOUND

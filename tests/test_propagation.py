from collections.abc import Iterator

import pytest
from fastapi import Depends, FastAPI, Request, status
from fastapi.testclient import TestClient

from fastapi_has_permissions import Permission, PermissionWrapper, fail
from fastapi_has_permissions._results import SkipPermissionCheck

app = FastAPI()


class AlwaysPass(Permission):
    async def check_permissions(self) -> bool:
        return True


class AlwaysSkip(Permission):
    async def check_permissions(self) -> bool:
        raise SkipPermissionCheck(reason="always skip")


class HasAuthorizationHeader(Permission):
    async def check_permissions(self, request: Request) -> bool:
        return "Authorization" in request.headers


class ResourceExists(Permission):
    default_exc_message = "Resource not found"
    default_exc_status_code = status.HTTP_404_NOT_FOUND

    async def check_permissions(self, request: Request) -> bool:
        return "resource" in request.headers


class ExplicitReason(Permission):
    async def check_permissions(self) -> bool:
        fail("explicit failure reason")


@app.get(
    "/and-propagates-status",
    dependencies=[
        Depends(AlwaysPass() & ResourceExists()),
    ],
)
@app.get(
    "/and-propagates-reason",
    dependencies=[
        Depends(AlwaysPass() & ExplicitReason()),
    ],
)
@app.get(
    "/or-aggregates-reasons",
    dependencies=[
        Depends(ExplicitReason() | HasAuthorizationHeader()),
    ],
)
@app.get(
    "/or-single-failure-propagates",
    dependencies=[
        Depends(AlwaysSkip() | ResourceExists()),
    ],
)
@app.get(
    "/wrapper-status-wins",
    dependencies=[
        Depends(
            PermissionWrapper(ResourceExists(), status_code=status.HTTP_403_FORBIDDEN),
        ),
    ],
)
@app.get(
    "/not-and-skip-and-pass",
    dependencies=[
        Depends(~(AlwaysSkip() & AlwaysPass())),
    ],
)
@app.get(
    "/not-and-all-skip",
    dependencies=[
        Depends(~(AlwaysSkip() & AlwaysSkip())),
    ],
)
@app.get(
    "/not-and-skip-and-fail",
    dependencies=[
        Depends(~(AlwaysSkip() & HasAuthorizationHeader())),
    ],
)
async def route() -> str:
    return "You have access to this endpoint!"


@pytest.fixture(scope="session")
def app_client() -> Iterator[TestClient]:
    with TestClient(app) as client:
        yield client


@pytest.mark.parametrize(
    ("endpoint", "headers", "expected_status", "expected_detail"),
    [
        pytest.param(
            "/and-propagates-status",
            {},
            status.HTTP_404_NOT_FOUND,
            "Resource not found",
            id="and-propagates-child-status-and-message",
        ),
        pytest.param(
            "/and-propagates-status",
            {"resource": "some-resource"},
            status.HTTP_200_OK,
            None,
            id="and-passes-when-all-pass",
        ),
        pytest.param(
            "/and-propagates-reason",
            {},
            status.HTTP_403_FORBIDDEN,
            "explicit failure reason",
            id="and-propagates-fail-reason",
        ),
        pytest.param(
            "/or-aggregates-reasons",
            {},
            status.HTTP_403_FORBIDDEN,
            "explicit failure reason; Permission denied",
            id="or-aggregates-all-branch-reasons",
        ),
        pytest.param(
            "/or-single-failure-propagates",
            {},
            status.HTTP_404_NOT_FOUND,
            "Resource not found",
            id="or-single-failure-propagates-status",
        ),
        pytest.param(
            "/or-single-failure-propagates",
            {"resource": "some-resource"},
            status.HTTP_200_OK,
            None,
            id="or-passes-when-branch-passes",
        ),
        pytest.param(
            "/wrapper-status-wins",
            {},
            status.HTTP_403_FORBIDDEN,
            "Resource not found",
            id="explicit-wrapper-status-overrides-child-status",
        ),
    ],
)
def test_propagation(endpoint, headers, expected_status, expected_detail, app_client) -> None:
    response = app_client.get(endpoint, headers=headers)

    assert response.status_code == expected_status

    if expected_detail is not None:
        assert response.json()["detail"] == expected_detail


@pytest.mark.parametrize(
    ("endpoint", "headers", "expected_status"),
    [
        pytest.param(
            "/not-and-skip-and-pass",
            {},
            status.HTTP_403_FORBIDDEN,
            id="not-of-and-with-skip-and-pass-denies",
        ),
        pytest.param(
            "/not-and-all-skip",
            {},
            status.HTTP_200_OK,
            id="not-of-fully-skipped-and-skips",
        ),
        pytest.param(
            "/not-and-skip-and-fail",
            {},
            status.HTTP_200_OK,
            id="not-of-and-with-skip-and-fail-allows",
        ),
        pytest.param(
            "/not-and-skip-and-fail",
            {"Authorization": "some-token"},
            status.HTTP_403_FORBIDDEN,
            id="not-of-and-with-skip-and-pass-header-denies",
        ),
    ],
)
def test_skip_truth_table_under_not(endpoint, headers, expected_status, app_client) -> None:
    response = app_client.get(endpoint, headers=headers)
    assert response.status_code == expected_status

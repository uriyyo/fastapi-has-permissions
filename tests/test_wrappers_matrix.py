from collections.abc import Callable, Iterator
from enum import IntEnum, StrEnum
from typing import Annotated

import pytest
from fastapi import Depends, FastAPI, Header, status
from fastapi.testclient import TestClient

from fastapi_has_permissions import (
    Advisory,
    AllowSkipped,
    DenySkipped,
    Dep,
    FailOnExc,
    LazyPermission,
    Permission,
    PermissionWrapper,
    SkipOnExc,
    WithError,
    add_permissions,
    fail,
    lazy,
    permission,
    skip,
)


class Behaviour(StrEnum):
    PASS = "pass"  # noqa: S105
    FAIL = "fail"
    SKIP = "skip"
    RAISE = "raise"


class Status(IntEnum):
    OK = status.HTTP_200_OK
    DENIED = status.HTTP_403_FORBIDDEN
    NOT_FOUND = status.HTTP_404_NOT_FOUND
    UNAVAILABLE = status.HTTP_503_SERVICE_UNAVAILABLE


class BackendError(Exception):
    pass


async def act(behaviour: Behaviour) -> bool:
    if behaviour is Behaviour.FAIL:
        fail("the check said no")

    if behaviour is Behaviour.SKIP:
        skip("the check has no opinion")

    if behaviour is Behaviour.RAISE:
        raise BackendError("the backend is down")

    return True


class Simple(Permission):
    behaviour: Behaviour

    async def check_permissions(self) -> bool:
        return await act(self.behaviour)


class SimpleLazy(LazyPermission):
    behaviour: Behaviour

    async def check_permissions(self) -> bool:
        return await act(self.behaviour)


async def value_dep() -> str:
    return "from dependency"


class UsesDep(Permission):
    behaviour: Behaviour
    dep: Dep[str]

    async def check_permissions(self, value: str, /) -> bool:
        assert value == "from dependency"

        return await act(self.behaviour)


class NamedWrapper(PermissionWrapper):
    pass


class NeedsHeader(Permission):
    async def check_permissions(self, x_token: Annotated[str, Header()]) -> bool:
        return bool(x_token)


def func_based(behaviour: Behaviour) -> Permission:
    @permission
    async def check() -> bool:
        return await act(behaviour)

    return check()


def guarded(behaviour: Behaviour) -> Permission:
    return FailOnExc(
        Simple(behaviour),
        (BackendError,),
        message="Backend unavailable",
        status_code=Status.UNAVAILABLE,
    )


INVERTED = {Behaviour.PASS: Behaviour.FAIL, Behaviour.FAIL: Behaviour.PASS}

KINDS: dict[str, Callable[[Behaviour], Permission]] = {
    "class-based": Simple,
    "function-based": func_based,
    "with-dep-field": lambda behaviour: UsesDep(behaviour, Depends(value_dep)),
    "lazy-wrapped": lambda behaviour: lazy(Simple(behaviour)),
    "lazy-subclass": SimpleLazy,
    "named-wrapper": lambda behaviour: NamedWrapper(Simple(behaviour)),
    "and-composite": lambda behaviour: Simple(behaviour) & Simple(behaviour),
    "or-composite": lambda behaviour: Simple(behaviour) | Simple(behaviour),
    "not-composite": lambda behaviour: ~Simple(INVERTED.get(behaviour, behaviour)),
    "nested-composite": lambda behaviour: (Simple(behaviour) & Simple(behaviour)) | Simple(behaviour),
}

WRAPPERS: dict[str, tuple[Callable[[Permission], Permission], dict[Behaviour, Status]]] = {
    "allow-skipped": (
        AllowSkipped,
        {Behaviour.PASS: Status.OK, Behaviour.FAIL: Status.DENIED, Behaviour.SKIP: Status.OK},
    ),
    "deny-skipped": (
        DenySkipped,
        {Behaviour.PASS: Status.OK, Behaviour.FAIL: Status.DENIED, Behaviour.SKIP: Status.DENIED},
    ),
    "advisory": (
        lambda perm: AllowSkipped(Advisory(perm)),
        {Behaviour.PASS: Status.OK, Behaviour.FAIL: Status.OK, Behaviour.SKIP: Status.OK},
    ),
    "with-error": (
        lambda perm: WithError(perm, status_code=Status.NOT_FOUND),
        {Behaviour.PASS: Status.OK, Behaviour.FAIL: Status.NOT_FOUND, Behaviour.SKIP: Status.NOT_FOUND},
    ),
    "fail-on-exc": (
        lambda perm: FailOnExc(perm, (BackendError,), status_code=Status.UNAVAILABLE),
        {
            Behaviour.PASS: Status.OK,
            Behaviour.FAIL: Status.UNAVAILABLE,
            Behaviour.SKIP: Status.UNAVAILABLE,
            Behaviour.RAISE: Status.UNAVAILABLE,
        },
    ),
    "skip-on-exc": (
        lambda perm: AllowSkipped(SkipOnExc(perm, (BackendError,))),
        {
            Behaviour.PASS: Status.OK,
            Behaviour.FAIL: Status.DENIED,
            Behaviour.SKIP: Status.OK,
            Behaviour.RAISE: Status.OK,
        },
    ),
}

app = FastAPI()
add_permissions(app)


async def route() -> str:
    return "You have access to this endpoint!"


def add_route(endpoint: str, perm: Permission, expected_status: Status, test_id: str) -> pytest.param:
    app.get(endpoint, dependencies=[Depends(perm)])(route)

    return pytest.param(endpoint, expected_status, id=test_id)


KIND_CASES = [
    add_route(f"/{kind}/{behaviour}", factory(behaviour), expected_status, f"{kind}-{behaviour}")
    for kind, factory in KINDS.items()
    for behaviour, expected_status in (
        (Behaviour.PASS, Status.OK),
        (Behaviour.FAIL, Status.DENIED),
        (Behaviour.SKIP, Status.DENIED),
    )
]

WRAPPER_CASES = [
    add_route(
        f"/{wrapper}/{kind}/{behaviour}",
        wrap(factory(behaviour)),
        expected_status,
        f"{wrapper}-{kind}-{behaviour}",
    )
    for kind, factory in KINDS.items()
    for wrapper, (wrap, expected) in WRAPPERS.items()
    for behaviour, expected_status in expected.items()
]


@app.get(
    "/nested-wrappers",
    dependencies=[
        Depends(
            WithError(
                AllowSkipped(Simple(Behaviour.SKIP)) & DenySkipped(Simple(Behaviour.PASS)), status_code=Status.NOT_FOUND
            )
        ),
    ],
)
@app.get(
    "/nested-wrappers-denied",
    dependencies=[
        Depends(
            WithError(
                AllowSkipped(Simple(Behaviour.SKIP)) & DenySkipped(Simple(Behaviour.SKIP)), status_code=Status.NOT_FOUND
            )
        ),
    ],
)
@app.get(
    "/nested-fail-on-exc-denies",
    dependencies=[
        Depends(guarded(Behaviour.FAIL) & Simple(Behaviour.PASS)),
    ],
)
@app.get(
    "/nested-fail-on-exc-raises",
    dependencies=[
        Depends(guarded(Behaviour.RAISE) & Simple(Behaviour.PASS)),
    ],
)
@app.get(
    "/plain-header",
    dependencies=[
        Depends(NeedsHeader()),
    ],
)
@app.get(
    "/wrapped-header",
    dependencies=[
        Depends(AllowSkipped(NeedsHeader())),
    ],
)
async def extra_route() -> str:
    return "You have access to this endpoint!"


@pytest.fixture(scope="session")
def app_client() -> Iterator[TestClient]:
    with TestClient(app) as client:
        yield client


@pytest.mark.parametrize(("endpoint", "expected_status"), KIND_CASES)
def test_permission_kinds(endpoint, expected_status, app_client) -> None:
    response = app_client.get(endpoint)

    assert response.status_code == expected_status


@pytest.mark.parametrize(("endpoint", "expected_status"), WRAPPER_CASES)
def test_wrappers_over_every_permission_kind(endpoint, expected_status, app_client) -> None:
    response = app_client.get(endpoint)

    assert response.status_code == expected_status


@pytest.mark.parametrize(
    ("endpoint", "expected_status", "expected_detail"),
    [
        pytest.param("/nested-wrappers", Status.OK, None, id="nested-wrappers"),
        pytest.param("/nested-wrappers-denied", Status.NOT_FOUND, None, id="nested-wrappers-denied"),
        pytest.param(
            "/nested-fail-on-exc-denies",
            Status.DENIED,
            "the check said no",
            id="nested-fail-on-exc-keeps-child-error",
        ),
        pytest.param(
            "/nested-fail-on-exc-raises",
            Status.UNAVAILABLE,
            "Backend unavailable",
            id="nested-fail-on-exc-uses-own-error",
        ),
    ],
)
def test_wrappers_nested_in_a_composition(endpoint, expected_status, expected_detail, app_client) -> None:
    response = app_client.get(endpoint)

    assert response.status_code == expected_status

    if expected_detail is not None:
        assert response.json()["detail"] == expected_detail


def test_wrapper_keeps_openapi_parameters() -> None:
    paths = app.openapi()["paths"]

    assert paths["/wrapped-header"]["get"]["parameters"] == paths["/plain-header"]["get"]["parameters"]
    assert [param["name"] for param in paths["/wrapped-header"]["get"]["parameters"]] == ["x-token"]

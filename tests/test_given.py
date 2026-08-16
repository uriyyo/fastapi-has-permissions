import uuid
from collections.abc import Iterator
from typing import Annotated

import pytest
from fastapi import Depends, FastAPI, Path, status
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
from fastapi_injected import is_dep, push_inject_scope, unwrap_dep_dependency

from fastapi_has_permissions import (
    Dep,
    Given,
    Permission,
    add_permissions,
    evaluate,
    is_failed,
    is_successful,
)

OWNER = uuid.UUID("00000000-0000-0000-0000-00000000000a")
OTHER = uuid.UUID("00000000-0000-0000-0000-00000000000b")

STUDENTS = {
    uuid.UUID("00000000-0000-0000-0000-000000000001"): OWNER,
    uuid.UUID("00000000-0000-0000-0000-000000000002"): OTHER,
}

resolved_actors = 0


async def get_actor() -> uuid.UUID:
    global resolved_actors  # noqa: PLW0603
    resolved_actors += 1
    return OWNER


ActorDep = Annotated[uuid.UUID, Depends(get_actor)]
FromPathStudentId = Annotated[uuid.UUID, Path(alias="student_id")]


class OwnsStudent(Permission):
    student_id: Dep[uuid.UUID]

    async def check_permissions(self, student_id: uuid.UUID, /, actor: ActorDep) -> bool:
        return STUDENTS.get(student_id) == actor


app = FastAPI()
add_permissions(app)


# the same rule, reached through the request
@app.get("/students/{student_id}", dependencies=[Depends(OwnsStudent(FromPathStudentId))])
async def read_student(student_id: uuid.UUID) -> str:
    return str(student_id)


@pytest.fixture(scope="session")
def app_client() -> Iterator[TestClient]:
    with TestClient(app) as client:
        yield client


@pytest.mark.asyncio
async def test_given_evaluates_off_request() -> None:
    # the point of `Given` - no request, no scope, no path params
    assert is_successful(await evaluate(OwnsStudent(Given(uuid.UUID(int=1)))))
    assert is_failed(await evaluate(OwnsStudent(Given(uuid.UUID(int=2)))))


@pytest.mark.asyncio
async def test_dep_marker_still_needs_a_request() -> None:
    # the contrast that motivates `Given` - a request-bound marker cannot resolve
    # off-request, because the fabricated scope carries no path params
    with pytest.raises(RequestValidationError):
        await evaluate(OwnsStudent(FromPathStudentId))


@pytest.mark.parametrize(
    ("student_id", "expected_status"),
    [
        pytest.param(uuid.UUID(int=1), status.HTTP_200_OK, id="owned"),
        pytest.param(uuid.UUID(int=2), status.HTTP_403_FORBIDDEN, id="not-owned"),
    ],
)
def test_same_rule_serves_the_route(student_id, expected_status, app_client) -> None:
    response = app_client.get(f"/students/{student_id}")

    assert response.status_code == expected_status


def test_given_is_a_dep() -> None:
    # `Given` produces the same kind of marker as `DepFactory` or an `Annotated` dep,
    # so everything that inspects a dep value keeps working
    given = Given(OWNER)

    assert is_dep(given)
    assert unwrap_dep_dependency(given).value == OWNER


def test_given_is_value_equal() -> None:
    assert Given(OWNER) == Given(OWNER)
    assert Given(OWNER) != Given(OTHER)
    assert OwnsStudent(Given(OWNER)) == OwnsStudent(Given(OWNER))


def test_given_hashes_by_value_with_an_identity_fallback() -> None:
    assert hash(Given(OWNER)) == hash(Given(OWNER))
    # an unhashable value falls back to identity rather than raising
    assert isinstance(hash(Given([1, 2])), int)


@pytest.mark.asyncio
async def test_given_shares_one_cache_entry_per_scope() -> None:
    permission = OwnsStudent(Given(uuid.UUID(int=1)))
    before = resolved_actors

    async with push_inject_scope():
        for _ in range(3):
            assert is_successful(await evaluate(permission))

    # the constant is value-equal, so the actor alongside it resolves once for the scope
    assert resolved_actors - before == 1

import uuid
from typing import Annotated

import pytest
from fastapi import FastAPI, Header, Path, Request
from fastapi.testclient import TestClient

from fastapi_has_permissions import (
    Dep,
    DependencyResolutionError,
    FailUnresolved,
    Given,
    Permission,
    SkipUnresolved,
    SyntheticScopeError,
    add_permissions,
    evaluate,
    is_failed,
    is_skipped,
    is_successful,
)

pytestmark = pytest.mark.asyncio

OWNER = uuid.UUID(int=1)

FromPath = Annotated[uuid.UUID, Path(alias="student_id")]


class OwnsStudent(Permission):
    student_id: Dep[uuid.UUID] = FromPath

    async def check_permissions(self, student_id: uuid.UUID, /) -> bool:
        return student_id == OWNER


class NeedsActor(Permission):
    async def check_permissions(self, actor: Annotated[str | None, Header()] = None) -> bool:
        return actor == "admin"


async def test_a_request_bound_dependency_cannot_resolve_off_request() -> None:
    with pytest.raises(DependencyResolutionError):
        await evaluate(OwnsStudent())


async def test_strict_refuses_a_fabricated_request() -> None:
    # the hazard: `actor` tolerates absence, so without strict this is an ordinary denial
    assert is_failed(await evaluate(NeedsActor()))

    async with evaluate.scope(strict=True) as ev:
        with pytest.raises(SyntheticScopeError):
            await ev(NeedsActor())


async def test_strict_accepts_a_real_request() -> None:
    app = FastAPI()
    add_permissions(app)

    @app.get("/strict")
    async def route() -> bool:
        async with evaluate.scope(strict=True) as ev:
            return is_successful(await ev(NeedsActor()))

    with TestClient(app) as client:
        assert client.get("/strict", headers={"actor": "admin"}).json() is True
        assert client.get("/strict").json() is False


async def test_strict_accepts_a_request_passed_explicitly() -> None:
    app = FastAPI()
    add_permissions(app)

    @app.get("/students/{student_id}")
    async def route(student_id: uuid.UUID, req: Request) -> bool:  # noqa: ARG001
        async with evaluate.scope(request=req, strict=True) as ev:
            return is_successful(await ev(OwnsStudent()))

    with TestClient(app) as client:
        assert client.get(f"/students/{OWNER}").json() is True
        assert client.get(f"/students/{uuid.UUID(int=2)}").json() is False


async def test_strict_is_carried_into_nested_scopes() -> None:
    async with evaluate.scope(strict=True) as ev, ev.scope() as nested:
        assert nested.strict


async def test_strict_can_be_turned_off_for_a_block() -> None:
    async with evaluate.scope(strict=True) as ev, ev.scope(strict=False) as lenient:
        assert is_failed(await lenient(NeedsActor()))


async def test_unresolved_wrappers_read_the_failure_two_ways() -> None:
    assert is_skipped(await evaluate(SkipUnresolved(OwnsStudent())))
    assert is_failed(await evaluate(FailUnresolved(OwnsStudent())))


async def test_unresolved_wrappers_leave_a_resolvable_check_alone() -> None:
    resolvable = OwnsStudent(Given(OWNER))

    assert is_successful(await evaluate(SkipUnresolved(resolvable)))
    assert is_successful(await evaluate(FailUnresolved(resolvable)))


async def test_unresolved_wrappers_do_not_rewrite_an_ordinary_denial() -> None:
    denied = OwnsStudent(Given(uuid.UUID(int=2)))

    assert is_failed(await evaluate(SkipUnresolved(denied)))
    assert is_failed(await evaluate(FailUnresolved(denied)))


async def test_app_is_available_to_dependencies_off_request() -> None:
    app = FastAPI()
    app.state.tenant = "acme"

    class MatchesTenant(Permission):
        async def check_permissions(self, request: Request) -> bool:
            return request.app.state.tenant == "acme"

    async with evaluate.scope(app=app) as ev:
        assert is_successful(await ev(MatchesTenant()))

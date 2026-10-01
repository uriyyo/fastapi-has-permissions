import gc
import weakref
from collections.abc import Callable
from typing import Annotated

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from fastapi_has_permissions import (
    Dep,
    Given,
    Permission,
    PermissionDeniedError,
    Resolved,
    SkipUnresolved,
    add_permissions,
    evaluate,
    permission,
)


class Record:
    # stands in for what a request hands a check - an actor, a record, a repository
    def __init__(self, *, allowed: bool = True) -> None:
        self.allowed = allowed


async def get_role() -> str:
    return "admin"


RoleDep = Annotated[str, Depends(get_role)]


class Allowed(Permission):
    record: Dep[Record]

    async def check_permissions(self, record: Record, /, role: RoleDep) -> bool:
        return record.allowed and role == "admin"


async def allowed(record: Resolved[Record], /) -> bool:
    return record.allowed


RULES: dict[str, Callable[[Record], Permission]] = {
    "leaf": lambda record: Allowed(Given(record)),
    "all": lambda record: Allowed(Given(record)) & Allowed(Given(record)),
    "any": lambda record: Allowed(Given(Record(allowed=False))) | Allowed(Given(record)),
    "not": lambda record: ~~Allowed(Given(record)),
    "func": lambda record: permission(allowed)(Given(record)),
    "wrapped": lambda record: SkipUnresolved(Allowed(Given(record))),
}


def _alive(refs: list[weakref.ref[Record]]) -> list[Record]:
    gc.collect()

    return [record for ref in refs if (record := ref()) is not None]


@pytest.mark.asyncio
@pytest.mark.parametrize("rule", RULES.values(), ids=RULES.keys())
async def test_checks_do_not_keep_what_they_were_given(rule: Callable[[Record], Permission]) -> None:
    refs = []

    for _ in range(3):
        record = Record()
        refs.append(weakref.ref(record))

        assert await evaluate.check(rule(record))

        del record

    assert not _alive(refs)


@pytest.mark.asyncio
async def test_denials_do_not_keep_what_they_were_given() -> None:
    refs = []

    for _ in range(3):
        record = Record(allowed=False)
        refs.append(weakref.ref(record))

        with pytest.raises(PermissionDeniedError):
            await evaluate.require(Allowed(Given(record)))

        del record

    assert not _alive(refs)


@pytest.mark.asyncio
async def test_checks_under_overrides_do_not_keep_what_they_were_given() -> None:
    refs = []

    for _ in range(3):
        record = Record()
        refs.append(weakref.ref(record))

        async with evaluate.scope({get_role: "admin"}) as perms:
            assert await perms.check(Allowed(Given(record)))

        del record

    assert not _alive(refs)


app = FastAPI()
add_permissions(app)
refs: list[weakref.ref[Record]] = []


@app.get("/records")
async def read_record() -> bool:
    # what a service does mid-request: check a rule on a record it already loaded
    record = Record()
    refs.append(weakref.ref(record))

    return await evaluate.check(Allowed(Given(record)))


def test_checks_inside_a_request_do_not_outlive_it() -> None:
    with TestClient(app) as client:
        for _ in range(3):
            assert client.get("/records").json() is True

    assert not _alive(refs)

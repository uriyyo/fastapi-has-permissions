from collections.abc import Iterator
from typing import Annotated

import pytest
from fastapi import Depends, FastAPI, Header, status
from fastapi.testclient import TestClient
from fastapi_injected import push_overrides

from fastapi_has_permissions import (
    AllowSkipped,
    Permission,
    When,
    add_permissions,
    evaluate,
    is_failed,
    is_skipped,
    is_successful,
    skip,
)

ran: list[str] = []


async def get_actor_kind(x_actor: Annotated[str | None, Header()] = None) -> str:
    return x_actor or "machine"


ActorKindDep = Annotated[str, Depends(get_actor_kind)]


class IsKind(Permission):
    kind: str

    async def check_permissions(self, actor_kind: ActorKindDep) -> bool:
        return actor_kind == self.kind


class Rule(Permission):
    name: str
    allow: bool = True

    async def check_permissions(self) -> bool:
        ran.append(self.name)
        return self.allow


class SkippingGuard(Permission):
    async def check_permissions(self) -> bool:
        skip("guard abstained")


def dispatch(*, owns: bool = True) -> Permission:
    return (
        When(IsKind("teacher"), Rule("OwnsStudent", allow=owns))
        | When(IsKind("student"), Rule("StudentIsSelf"))
        | When(IsKind("capability"), Rule("GrantCovers"))
    )


app = FastAPI()
add_permissions(app)


@app.get("/dispatch", dependencies=[Depends(dispatch())])
async def dispatch_route() -> str:
    return "You have access to this endpoint!"


@pytest.fixture(scope="session")
def app_client() -> Iterator[TestClient]:
    with TestClient(app) as client:
        yield client


@pytest.fixture(autouse=True)
def _clear_ran() -> None:
    ran.clear()


@pytest.mark.asyncio
async def test_an_applicable_guard_lets_the_rule_decide() -> None:
    with push_overrides({get_actor_kind: "teacher"}):
        assert is_successful(await evaluate(When(IsKind("teacher"), Rule("allows"))))

    with push_overrides({get_actor_kind: "teacher"}):
        assert is_failed(await evaluate(When(IsKind("teacher"), Rule("denies", allow=False))))


@pytest.mark.asyncio
async def test_an_inapplicable_guard_abstains_without_running_the_rule() -> None:
    with push_overrides({get_actor_kind: "student"}):
        result = await evaluate(When(IsKind("teacher"), Rule("OwnsStudent")))

    # the distinction the wrapper exists for: not denied, simply not applicable
    assert is_skipped(result)
    assert ran == []


@pytest.mark.asyncio
async def test_a_skipping_guard_also_abstains() -> None:
    result = await evaluate(When(SkippingGuard(), Rule("OwnsStudent")))

    assert is_skipped(result)
    assert result.reason == "guard abstained"
    assert ran == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("actor", "expected"),
    [
        pytest.param("teacher", ["OwnsStudent"], id="teacher"),
        pytest.param("student", ["StudentIsSelf"], id="student"),
        pytest.param("capability", ["GrantCovers"], id="capability"),
    ],
)
async def test_exactly_one_branch_runs(actor, expected) -> None:
    with push_overrides({get_actor_kind: actor}):
        assert is_successful(await evaluate(dispatch()))

    assert ran == expected


@pytest.mark.asyncio
async def test_no_applicable_branch_denies() -> None:
    # fail-closed: an actor no branch claims is denied, not allowed
    with push_overrides({get_actor_kind: "machine"}):
        result = await evaluate(dispatch())

    assert is_skipped(result)
    assert ran == []


@pytest.mark.asyncio
async def test_an_applicable_branch_can_still_deny() -> None:
    with push_overrides({get_actor_kind: "teacher"}):
        assert is_failed(await evaluate(dispatch(owns=False)))

    assert ran == ["OwnsStudent"]


@pytest.mark.asyncio
async def test_skip_means_allow_is_opt_in() -> None:
    with push_overrides({get_actor_kind: "machine"}):
        assert is_successful(await evaluate(AllowSkipped(dispatch())))


@pytest.mark.parametrize(
    ("actor", "expected_status"),
    [
        pytest.param("teacher", status.HTTP_200_OK, id="applicable"),
        pytest.param("machine", status.HTTP_403_FORBIDDEN, id="no-branch-applies"),
    ],
)
def test_dispatch_through_a_route(actor, expected_status, app_client) -> None:
    response = app_client.get("/dispatch", headers={"x-actor": actor})

    assert response.status_code == expected_status


def test_the_guard_reaches_the_schema(app_client) -> None:
    # the guard is a sub-permission, so its dependencies are documented like any other
    parameters = app_client.app.openapi()["paths"]["/dispatch"]["get"]["parameters"]

    assert "x-actor" in {parameter["name"] for parameter in parameters}

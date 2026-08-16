from typing import Annotated, ClassVar

import pytest
from fastapi import Depends, status

from fastapi_has_permissions import Permission, Skipped, When, evaluate, fail, skip
from fastapi_has_permissions.common import Allow, Deny
from fastapi_has_permissions.testing import assert_allowed, assert_denied, assert_skipped


async def get_actor_kind() -> str:
    return "machine"


ActorKindDep = Annotated[str, Depends(get_actor_kind)]


class IsKind(Permission):
    kind: str

    async def check_permissions(self, actor_kind: ActorKindDep) -> bool:
        return actor_kind == self.kind


class NotFound(Permission):
    default_exc_status_code: ClassVar[int] = status.HTTP_404_NOT_FOUND
    default_exc_code: ClassVar[str] = "student_inactive"

    async def check_permissions(self) -> bool:
        fail("no such student")


class Abstains(Permission):
    async def check_permissions(self) -> bool:
        skip("not my business")


@pytest.mark.asyncio
async def test_assert_allowed_passes_and_returns_the_result() -> None:
    assert await assert_allowed(Allow()) is True


@pytest.mark.asyncio
async def test_assert_denied_returns_the_failure() -> None:
    failed = await assert_denied(NotFound())

    assert failed.reason == "no such student"
    assert failed.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_assert_denied_checks_the_error_configuration() -> None:
    await assert_denied(
        NotFound(),
        reason="no such student",
        status_code=status.HTTP_404_NOT_FOUND,
        code="student_inactive",
    )


@pytest.mark.asyncio
async def test_assert_skipped_returns_the_abstention() -> None:
    assert await assert_skipped(Abstains(), reason="not my business") == Skipped("not my business")


@pytest.mark.asyncio
async def test_helpers_use_the_surrounding_scope() -> None:
    async with evaluate.scope({ActorKindDep: "teacher"}):
        await assert_allowed(IsKind("teacher"))
        await assert_denied(IsKind("student"))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("call", "expected"),
    [
        pytest.param(
            lambda: assert_allowed(Deny()),
            "Deny was expected to allow, but it denied with 403 'Permission denied'",
            id="allowed-but-denied",
        ),
        pytest.param(
            lambda: assert_allowed(Abstains()),
            "Abstains was expected to allow, but it abstained ('not my business'). Note that a skip "
            "denies at the root, but it is not a denial - use `assert_skipped` to assert an abstention",
            id="allowed-but-abstained",
        ),
        pytest.param(
            lambda: assert_denied(Allow()),
            "Allow was expected to deny, but it allowed",
            id="denied-but-allowed",
        ),
        pytest.param(
            lambda: assert_skipped(Deny()),
            "Deny was expected to abstain, but it denied with 403 'Permission denied'",
            id="skipped-but-denied",
        ),
        pytest.param(
            lambda: assert_denied(NotFound(), status_code=403),
            "NotFound denied, but its status_code was 404 rather than the expected 403",
            id="wrong-status-code",
        ),
        pytest.param(
            lambda: assert_skipped(Abstains(), reason="other"),
            "Abstains abstained, but its reason was 'not my business' rather than the expected 'other'",
            id="wrong-skip-reason",
        ),
    ],
)
async def test_failure_messages_say_what_happened(call, expected) -> None:
    with pytest.raises(AssertionError) as exc_info:
        await call()

    assert str(exc_info.value) == expected


@pytest.mark.asyncio
async def test_an_abstention_is_not_accepted_as_a_denial() -> None:
    # the distinction `When` is built on: a rule that stopped applying must not pass as a
    # rule that refused, even though both deny at the root
    inapplicable = When(IsKind("teacher"), Deny())

    with pytest.raises(AssertionError, match="use `assert_skipped`"):
        await assert_denied(inapplicable)

    await assert_skipped(inapplicable)

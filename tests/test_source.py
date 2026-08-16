from typing import Annotated, ClassVar

import pytest
from fastapi import Depends

from fastapi_has_permissions import (
    Advisory,
    Failed,
    Permission,
    PermissionDeniedError,
    Skipped,
    Source,
    When,
    evaluate,
    fail,
    skip,
)
from fastapi_has_permissions.common import Allow, Deny


async def get_actor_kind() -> str:
    return "student"


ActorKindDep = Annotated[str, Depends(get_actor_kind)]


class IsKind(Permission):
    kind: str

    async def check_permissions(self, actor_kind: ActorKindDep) -> bool:
        return actor_kind == self.kind


class IsStudent(Permission):
    async def check_permissions(self) -> bool:
        fail("not a student")


class IsTeacher(Permission):
    async def check_permissions(self) -> bool:
        skip("not applicable")


class OwnsStudent(Permission):
    async def check_permissions(self) -> bool:
        fail("student 42 is not yours")


class Renamed(Permission):
    __trace_name__: ClassVar[str] = "TheRule"

    async def check_permissions(self) -> bool:
        return False


async def trace(permission: Permission, /) -> str:
    result = await evaluate(permission)

    assert isinstance(result, Failed | Skipped)
    assert result.source is not None

    return str(result.source)


@pytest.mark.asyncio
async def test_a_leaf_records_its_own_outcome() -> None:
    assert await trace(IsStudent()) == "IsStudent[failed: not a student]"
    assert await trace(IsTeacher()) == "IsTeacher[skipped: not applicable]"
    assert await trace(Deny()) == "Deny[failed: Permission denied]"


@pytest.mark.asyncio
async def test_alternatives_render_as_a_chain() -> None:
    assert await trace(IsStudent() | IsTeacher()) == (
        "IsStudent[failed: not a student] | IsTeacher[skipped: not applicable]"
    )


@pytest.mark.asyncio
async def test_a_chain_records_the_branches_that_succeeded() -> None:
    # `&` short-circuits, so the trace stops at the failure but keeps what led to it
    assert await trace(Allow() & IsStudent() & Deny()) == ("Allow[success] & IsStudent[failed: not a student]")


@pytest.mark.asyncio
async def test_a_nested_group_is_parenthesised() -> None:
    assert await trace((IsStudent() | IsTeacher()) & Allow()) == (
        "(IsStudent[failed: not a student] | IsTeacher[skipped: not applicable])"
    )


@pytest.mark.asyncio
async def test_a_guard_says_why_a_branch_stepped_aside() -> None:
    dispatch = When(IsKind("teacher"), OwnsStudent()) | When(IsKind("capability"), Allow())

    assert await trace(dispatch) == (
        "When(IsKind[failed: Permission denied])[skipped: Permission denied]"
        " | When(IsKind[failed: Permission denied])[skipped: Permission denied]"
    )


@pytest.mark.asyncio
async def test_an_applicable_branch_reports_the_rule_that_denied() -> None:
    dispatch = When(IsKind("student"), OwnsStudent()) | When(IsKind("teacher"), Allow())

    assert await trace(dispatch) == (
        "OwnsStudent[failed: student 42 is not yours]"
        " | When(IsKind[failed: Permission denied])[skipped: Permission denied]"
    )


@pytest.mark.asyncio
async def test_a_wrapper_records_the_outcome_it_rewrote() -> None:
    assert await trace(Advisory(IsStudent())) == ("Advisory(IsStudent[failed: not a student])[skipped: not a student]")


@pytest.mark.asyncio
async def test_a_negation_records_what_it_inverted() -> None:
    assert await trace(~Allow()) == "NotPermission(Allow[success])[failed]"


@pytest.mark.asyncio
async def test_trace_name_overrides_the_class_name() -> None:
    assert await trace(Renamed()) == "TheRule[failed: Permission denied]"


@pytest.mark.asyncio
async def test_the_raised_error_carries_the_trace() -> None:
    with pytest.raises(PermissionDeniedError) as exc_info:
        await evaluate.require(IsStudent() | IsTeacher())

    assert str(exc_info.value.source) == ("IsStudent[failed: not a student] | IsTeacher[skipped: not applicable]")


def test_the_source_takes_no_part_in_equality() -> None:
    # a trace is diagnostic, so two denials of the same kind stay equal however they arose
    traced = Failed(reason="denied", source=Source("Somewhere", "failed"))

    assert traced == Failed(reason="denied")
    assert hash(traced) == hash(Failed(reason="denied"))
    assert Skipped(reason="x", source=Source("A", "skipped")) == Skipped(reason="x")

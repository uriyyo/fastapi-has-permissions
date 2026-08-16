from typing import Annotated, Literal

from fastapi_has_permissions import CheckResult, Evaluate, PermissionEvaluator, evaluate, is_successful

from .deps import (
    Allow,
    IsAdmin,
    RoleDep,
    TypeOf,
    is_equivalent_to,
    static_assert,
)

# `Evaluate` is the injectable form of the evaluator, so it behaves as one in annotations
static_assert(is_equivalent_to(Evaluate, PermissionEvaluator))
static_assert(is_equivalent_to(Annotated[PermissionEvaluator, "irrelevant"], Evaluate))


async def _evaluates(evaluator: Evaluate) -> None:
    static_assert(is_equivalent_to(TypeOf[await evaluate(Allow())], CheckResult))
    static_assert(is_equivalent_to(TypeOf[await evaluator(IsAdmin(RoleDep))], CheckResult))
    static_assert(is_equivalent_to(TypeOf[await evaluator.check(Allow())], bool))
    static_assert(is_equivalent_to(TypeOf[await evaluator.require(Allow())], CheckResult))

    # the result narrows like any other `CheckResult`
    result = await evaluator(Allow())

    if is_successful(result):
        static_assert(is_equivalent_to(TypeOf[result], Literal[True]))


async def _negatives() -> None:
    await evaluate("a permission")  # type: ignore[ty:invalid-argument-type]
    await PermissionEvaluator().check(RoleDep)  # type: ignore[ty:invalid-argument-type]

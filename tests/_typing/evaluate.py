from typing import Annotated, Literal

from fastapi_has_permissions import (
    CheckResult,
    Eval,
    Evaluate,
    PermissionEvaluator,
    evaluate,
    is_successful,
)

from .deps import (
    Allow,
    Doc,
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


# `Eval[T, permission]` annotates as its first argument - the permission rides along as
# metadata, the same way `DepFactory[T, factory]` carries its factory
static_assert(is_equivalent_to(Eval[CheckResult, Allow()], CheckResult))
static_assert(is_equivalent_to(Eval[CheckResult, IsAdmin(RoleDep)], CheckResult))
static_assert(is_equivalent_to(Eval[bool, Allow()], bool))


async def _evaluates_in_a_route(result: Eval[CheckResult, Allow()]) -> None:
    if is_successful(result):
        static_assert(is_equivalent_to(TypeOf[result], Literal[True]))


# the module-level `evaluate` is an evaluator, so it carries the same API as the injected one
static_assert(is_equivalent_to(TypeOf[evaluate], PermissionEvaluator))


async def _scoped() -> None:
    async with evaluate.scope({RoleDep: "admin"}) as perms:
        static_assert(is_equivalent_to(TypeOf[perms], PermissionEvaluator))
        static_assert(is_equivalent_to(TypeOf[await perms.check(Allow())], bool))

    # `filter` keeps the item type of whatever it was given
    async with evaluate.scope() as perms:
        static_assert(is_equivalent_to(TypeOf[await perms.filter([Doc()], lambda _: Allow())], list[Doc]))
        static_assert(is_equivalent_to(TypeOf[await perms.filter(["a"], lambda _: Allow())], list[str]))


async def _scope_negatives() -> None:
    async with evaluate.scope() as perms:
        # the factory has to produce a permission, not a bool
        await perms.filter([Doc()], lambda _: True)  # type: ignore[ty:invalid-argument-type]
        await perms.filter(Doc(), lambda _: Allow())  # type: ignore[ty:invalid-argument-type]

    evaluate.scope(on_failure=lambda _, __: "not an exception")  # type: ignore[ty:invalid-argument-type]

from typing import Literal

from fastapi_has_permissions import (
    CheckResult,
    Failed,
    Skipped,
    as_failed,
    fail,
    get_reason,
    is_failed,
    is_skipped,
    is_successful,
    skip,
)

from .deps import TypeOf, is_assignable_to, is_equivalent_to, static_assert

static_assert(is_equivalent_to(CheckResult, bool | Skipped | Failed))


def _narrow_skipped(result: CheckResult) -> None:
    if is_skipped(result):
        static_assert(is_equivalent_to(TypeOf[result], Skipped))
    else:
        # `Skipped` and `Failed` are unrelated classes rather than disjoint ones,
        # so the negative branch keeps a `~Skipped` intersection - assignability is the check that holds
        static_assert(is_assignable_to(TypeOf[result], bool | Failed))


def _narrow_failed(result: CheckResult) -> None:
    # a failure is either an explicit `Failed` or a plain `False`
    if is_failed(result):
        static_assert(is_equivalent_to(TypeOf[result], Failed | Literal[False]))
    else:
        static_assert(is_assignable_to(TypeOf[result], Literal[True] | Skipped))


def _narrow_successful(result: CheckResult) -> None:
    if is_successful(result):
        static_assert(is_equivalent_to(TypeOf[result], Literal[True]))
    else:
        static_assert(is_equivalent_to(TypeOf[result], Literal[False] | Skipped | Failed))


def _narrow_to_a_single_case(result: CheckResult) -> None:
    if is_skipped(result) or is_failed(result):
        return

    static_assert(is_equivalent_to(TypeOf[result], Literal[True]))


# `skip()` and `fail()` never return, so a check body may end with them
def _skips() -> bool:
    skip("no opinion")


def _fails() -> bool:
    fail("denied")


def _unreachable_after_skip() -> None:
    skip()

    # unreachable, so the deliberate type error below is never reported
    _never: int = "not an int"


_boolean: CheckResult = True

# `as_failed` always yields a `Failed`, whatever kind of result it was handed
static_assert(is_equivalent_to(TypeOf[as_failed(Skipped())], Failed))
static_assert(is_equivalent_to(TypeOf[as_failed(_boolean)], Failed))
static_assert(is_equivalent_to(TypeOf[as_failed(Failed(), Failed(reason="fallback"))], Failed))

# `get_reason` is defined for every result, and may find nothing
static_assert(is_equivalent_to(TypeOf[get_reason(Skipped())], str | None))
static_assert(is_equivalent_to(TypeOf[get_reason(_boolean)], str | None))


def _result_helper_negatives() -> None:
    as_failed(Skipped(), Skipped())  # type: ignore[ty:invalid-argument-type]
    get_reason("not a result")  # type: ignore[ty:invalid-argument-type]

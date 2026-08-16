from fastapi_has_permissions import CheckResult, Failed, Skipped
from fastapi_has_permissions.testing import assert_allowed, assert_denied, assert_skipped

from .deps import (
    Allow,
    RoleDep,
    TypeOf,
    is_equivalent_to,
    static_assert,
)


async def _asserts() -> None:
    # each helper returns the result it asserted, narrowed to what it proved
    static_assert(is_equivalent_to(TypeOf[await assert_allowed(Allow())], CheckResult))
    static_assert(is_equivalent_to(TypeOf[await assert_denied(Allow())], Failed))
    static_assert(is_equivalent_to(TypeOf[await assert_skipped(Allow())], Skipped))

    # the expectations are keyword-only and optional
    await assert_denied(Allow(), status_code=404, code="gone", reason="nope")
    await assert_skipped(Allow(), reason="not mine")


async def _negatives() -> None:
    await assert_allowed(RoleDep)  # type: ignore[ty:invalid-argument-type]
    await assert_denied(Allow(), status_code="404")  # type: ignore[ty:invalid-argument-type]
    await assert_skipped(Allow(), "not mine")  # type: ignore[ty:too-many-positional-arguments]

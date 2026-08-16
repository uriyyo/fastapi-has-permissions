from fastapi_has_permissions import (
    Advisory,
    AllowSkipped,
    CheckResult,
    DenySkipped,
    ExcHandler,
    FailOnExc,
    Permission,
    PermissionWrapper,
    ResultMapper,
    SkipOnExc,
    Undocumented,
    When,
    WithError,
)
from fastapi_has_permissions._wrappers import WhenPermission
from fastapi_has_permissions.types import Exceptions

from .deps import (
    Allow,
    Deny,
    IsAdmin,
    RoleDep,
    TypeOf,
    is_equivalent_to,
    is_subtype_of,
    static_assert,
)

# every wrapper is a permission wrapping a permission, so wrappers nest
static_assert(is_subtype_of(ResultMapper, PermissionWrapper))
static_assert(is_subtype_of(ExcHandler, PermissionWrapper))
static_assert(is_subtype_of(PermissionWrapper, Permission))

static_assert(is_equivalent_to(TypeOf[AllowSkipped(Allow())], AllowSkipped))
static_assert(is_equivalent_to(TypeOf[DenySkipped(Allow())], DenySkipped))
static_assert(is_equivalent_to(TypeOf[Advisory(Allow())], Advisory))
static_assert(is_equivalent_to(TypeOf[Undocumented(Allow())], Undocumented))
static_assert(is_equivalent_to(TypeOf[WithError(Allow(), message="nope")], WithError))
static_assert(is_equivalent_to(TypeOf[AllowSkipped(Advisory(Undocumented(IsAdmin(RoleDep))))], AllowSkipped))

# the wrapped permission is a positional field, the error config stays keyword-only
static_assert(is_equivalent_to(TypeOf[AllowSkipped(permission=Allow())], AllowSkipped))

# the exception handlers take a tuple of exception types alongside the permission
static_assert(is_equivalent_to(TypeOf[SkipOnExc(Allow(), (ValueError,))], SkipOnExc))
static_assert(is_equivalent_to(TypeOf[FailOnExc(Allow(), (ValueError, KeyError))], FailOnExc))
static_assert(is_equivalent_to(TypeOf[SkipOnExc(Allow(), exceptions=())], SkipOnExc))
static_assert(is_equivalent_to(Exceptions, tuple[type[BaseException], ...]))

# a wrapper composes like any other permission
static_assert(is_equivalent_to(TypeOf[AllowSkipped(Allow()) & Advisory(Allow())], Permission))


# `When` reads guard-first, and yields a permission like every other wrapper
static_assert(is_equivalent_to(TypeOf[When(Allow(), Deny())], WhenPermission))
static_assert(is_subtype_of(WhenPermission, Permission))
static_assert(is_equivalent_to(TypeOf[When(Allow(), Deny()) | When(Deny(), Allow())], Permission))


def _negatives() -> None:
    AllowSkipped()  # type: ignore[ty:missing-argument]
    AllowSkipped(RoleDep)  # type: ignore[ty:invalid-argument-type]

    When(Allow())  # type: ignore[ty:missing-argument]
    When(Allow(), RoleDep)  # type: ignore[ty:invalid-argument-type]
    When(RoleDep, Allow())  # type: ignore[ty:invalid-argument-type]

    SkipOnExc(Allow())  # type: ignore[ty:missing-argument]
    # a bare exception class, not a tuple of them
    SkipOnExc(Allow(), ValueError)  # type: ignore[ty:invalid-argument-type]
    FailOnExc(Allow(), ("ValueError",))  # type: ignore[ty:invalid-argument-type]


# `ResultMapper` / `ExcHandler` are the documented extension points ...
class _Custom(ResultMapper):
    def __map_result__(self, result: CheckResult, /) -> CheckResult:
        return result


static_assert(is_equivalent_to(TypeOf[_Custom(Allow())], _Custom))


# ... while the concrete wrappers are final
class _NotAllowed(AllowSkipped):  # type: ignore[ty:subclass-of-final-class]
    pass


class _AlsoNotAllowed(Undocumented):  # type: ignore[ty:subclass-of-final-class]
    pass

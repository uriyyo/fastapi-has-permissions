from fastapi_has_permissions import (
    AllPermissions,
    AnyPermissions,
    CheckResult,
    NotPermission,
    Permission,
    PermissionWrapper,
)
from fastapi_has_permissions.types import AsyncFunc

from .deps import (
    Allow,
    Deny,
    DocDep,
    IsAdmin,
    RoleDep,
    TypeOf,
    is_assignable_to,
    is_equivalent_to,
    is_subtype_of,
    static_assert,
)

# every built-in permission is a `Permission`
static_assert(is_subtype_of(TypeOf[Allow()], Permission))
static_assert(is_subtype_of(AllPermissions, Permission))
static_assert(is_subtype_of(AnyPermissions, Permission))
static_assert(is_subtype_of(NotPermission, Permission))
static_assert(is_subtype_of(PermissionWrapper, Permission))

# the combinators stay inside the `Permission` domain - the concrete composite class is
# an implementation detail, so they are declared as `Permission` rather than as `AllPermissions` etc
static_assert(is_equivalent_to(TypeOf[Allow() & Deny()], Permission))
static_assert(is_equivalent_to(TypeOf[Allow() | Deny()], Permission))
static_assert(is_equivalent_to(TypeOf[~Allow()], Permission))
static_assert(is_equivalent_to(TypeOf[~(Allow() & Deny()) | ~Deny()], Permission))

# `check_permissions` is exposed as an async callable returning a `CheckResult`
static_assert(is_assignable_to(TypeOf[Allow().check_permissions], AsyncFunc[CheckResult]))
static_assert(is_assignable_to(TypeOf[IsAdmin(RoleDep).check_permissions], AsyncFunc[CheckResult]))

# `MakeDataclass` gives every permission a dataclass `__init__` over its declared fields
static_assert(is_equivalent_to(TypeOf[IsAdmin(RoleDep)], IsAdmin))
static_assert(is_equivalent_to(TypeOf[IsAdmin(role_dep=RoleDep)], IsAdmin))

# the error config is keyword-only and inherited from `HTTPExcRaiser`
_configured = IsAdmin(
    RoleDep,
    message="nope",
    status_code=404,
    code="gone",
    headers={"WWW-Authenticate": "Bearer"},
)
static_assert(is_equivalent_to(TypeOf[_configured], IsAdmin))


def _negatives() -> None:
    IsAdmin()  # type: ignore[ty:missing-argument]
    IsAdmin(RoleDep, RoleDep)  # type: ignore[ty:too-many-positional-arguments]
    IsAdmin(DocDep)  # type: ignore[ty:invalid-argument-type]
    IsAdmin(RoleDep, status_code="404")  # type: ignore[ty:invalid-argument-type]

    Allow() & 1  # type: ignore[ty:unsupported-operator]
    Allow() | "nope"  # type: ignore[ty:unsupported-operator]

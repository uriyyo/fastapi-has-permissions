from fastapi_has_permissions import Permission, Requires
from fastapi_has_permissions._requires import RequiresDepends
from fastapi_has_permissions.common import Allow, Deny, HasRole, HasScope, IsAuthenticated

from .deps import (
    Doc,
    DocDep,
    RoleDep,
    TypeOf,
    is_equivalent_to,
    is_subtype_of,
    static_assert,
)

static_assert(is_subtype_of(Allow, Permission))
static_assert(is_subtype_of(Deny, Permission))
static_assert(is_subtype_of(IsAuthenticated, Permission))
static_assert(is_subtype_of(HasScope, Permission))
static_assert(is_subtype_of(HasRole, Permission))

# `Allow` / `Deny` take no fields, only the inherited keyword-only error config
static_assert(is_equivalent_to(TypeOf[Allow()], Allow))
static_assert(is_equivalent_to(TypeOf[Deny(message="no", status_code=404)], Deny))

# the rest take their dependency marker positionally
static_assert(is_equivalent_to(TypeOf[IsAuthenticated(RoleDep)], IsAuthenticated))
static_assert(is_equivalent_to(TypeOf[HasRole(RoleDep, ["admin"])], HasRole))
static_assert(is_equivalent_to(TypeOf[HasRole(RoleDep, "admin")], HasRole))
static_assert(is_equivalent_to(TypeOf[HasScope(RoleDep, {"read", "write"})], HasScope))
static_assert(is_equivalent_to(TypeOf[HasRole(role_dep=RoleDep, roles=["admin"])], HasRole))

# ... and they compose and slot into `Requires` like any other permission
static_assert(is_equivalent_to(TypeOf[IsAuthenticated(RoleDep) & HasRole(RoleDep, "admin")], Permission))
static_assert(is_equivalent_to(TypeOf[Requires(DocDep, HasRole(RoleDep, "admin"))], RequiresDepends[Doc]))


def _negatives() -> None:
    Allow(RoleDep)  # type: ignore[ty:too-many-positional-arguments]
    HasRole(RoleDep)  # type: ignore[ty:missing-argument]
    HasRole(RoleDep, 1)  # type: ignore[ty:invalid-argument-type]
    IsAuthenticated(RoleDep, message=404)  # type: ignore[ty:invalid-argument-type]

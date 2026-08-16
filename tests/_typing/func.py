from fastapi_has_permissions import CheckResult, Dep, Permission, Requires, Resolved, permission, skip
from fastapi_has_permissions._func import FuncPermission
from fastapi_has_permissions._requires import RequiresDepends

from .deps import (
    Doc,
    DocDep,
    RoleDep,
    TypeOf,
    is_equivalent_to,
    is_subtype_of,
    static_assert,
)

static_assert(is_subtype_of(FuncPermission, Permission))


# a check's parameters receive the *resolved* value, so they carry the resource type itself
@permission
async def is_admin(role: Resolved[str], /) -> bool:
    return role.casefold() == "admin"


@permission(message="not the owner", status_code=404, code="gone", headers={})
async def is_owner(doc: Resolved[Doc], role: Resolved[str], /) -> CheckResult:
    if not role:
        skip()

    return doc.name == role


# both forms of the decorator produce a factory that takes the dependency markers
static_assert(is_equivalent_to(TypeOf[is_admin(RoleDep)], FuncPermission))
static_assert(is_equivalent_to(TypeOf[is_owner(DocDep, RoleDep)], FuncPermission))

# ... and what it produces composes like any other permission
static_assert(is_equivalent_to(TypeOf[is_admin(RoleDep) | is_owner(DocDep, RoleDep)], Permission))
static_assert(is_equivalent_to(TypeOf[~is_admin(RoleDep)], Permission))
static_assert(is_equivalent_to(TypeOf[Requires(DocDep, is_admin(RoleDep))], RequiresDepends[Doc]))


def _negatives() -> None:
    # the decorated check must be async
    @permission  # type: ignore[ty:no-matching-overload]
    def _sync(role: Dep[str], /) -> bool:
        return role == "admin"

    permission("not a function")  # type: ignore[ty:no-matching-overload]
    permission(message=404)  # type: ignore[ty:invalid-argument-type]

    # `Dep[T]` is the marker as a value, so a parameter annotated with it is not a `T`
    @permission
    async def _marker_as_parameter(doc: Dep[Doc], /) -> bool:
        return doc.name == "owner"  # type: ignore[ty:unresolved-attribute]

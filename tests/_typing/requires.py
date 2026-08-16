from typing import Annotated

from fastapi.params import Depends

from fastapi_has_permissions import Requires, Resource
from fastapi_has_permissions._requires import RequiresDepends, RequiresResolver

from .deps import (
    Allow,
    Doc,
    DocDep,
    DocPolicy,
    IsAdmin,
    Other,
    OtherPolicy,
    RoleDep,
    TypeOf,
    is_equivalent_to,
    is_subtype_of,
    static_assert,
)

# the single-argument form takes the resource type from the policy
static_assert(is_equivalent_to(TypeOf[Requires(DocPolicy())], RequiresDepends[Doc]))
static_assert(is_equivalent_to(TypeOf[Requires(OtherPolicy())], RequiresDepends[Other]))

# ... and a named action does not change it
static_assert(is_equivalent_to(TypeOf[Requires(DocPolicy(), DocPolicy.publish)], RequiresDepends[Doc]))

# the two-argument form takes it from the resource dependency, against a policy or a permission
static_assert(is_equivalent_to(TypeOf[Requires(DocDep, DocPolicy())], RequiresDepends[Doc]))
static_assert(is_equivalent_to(TypeOf[Requires(DocDep, Allow())], RequiresDepends[Doc]))
static_assert(is_equivalent_to(TypeOf[Requires(DocDep, IsAdmin(RoleDep) | Allow())], RequiresDepends[Doc]))
static_assert(is_equivalent_to(TypeOf[Requires(RoleDep, Allow())], RequiresDepends[str]))

# the wiring stays introspectable: `RequiresDepends` is a `params.Depends` narrowing `dependency`
static_assert(is_subtype_of(RequiresDepends[Doc], Depends))
static_assert(is_equivalent_to(TypeOf[Requires(DocPolicy()).dependency], RequiresResolver[Doc]))
static_assert(is_equivalent_to(TypeOf[Requires(DocPolicy()).dependency.resource_dep], Resource[Doc]))

# `use_cache` is keyword-only
static_assert(is_equivalent_to(TypeOf[Requires(DocPolicy(), use_cache=False)], RequiresDepends[Doc]))


# the annotated form a route actually uses
async def _route(doc: Annotated[Doc, Requires(DocPolicy())]) -> Doc:
    return doc


def _negatives() -> None:
    # a policy class, not an instance
    Requires(DocPolicy)  # type: ignore[ty:invalid-argument-type]

    # a resource dependency with nothing to check it against
    Requires(DocDep)  # type: ignore[ty:invalid-argument-type]

    # a policy for a different resource than the dependency loads
    Requires(RoleDep, DocPolicy())  # type: ignore[ty:no-matching-overload]

    # neither a policy nor a permission
    Requires(DocDep, "read")  # type: ignore[ty:no-matching-overload]

    Requires(DocPolicy(), use_cache="yes")  # type: ignore[ty:invalid-argument-type]

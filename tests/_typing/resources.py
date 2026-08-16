from fastapi_has_permissions import Dep, Resolved, Resource

from .deps import (
    CallableTypeOf,
    Doc,
    DocDep,
    Other,
    RoleDep,
    TypeOf,
    get_doc,
    is_assignable_to,
    is_equivalent_to,
    static_assert,
)

# `Dep[R]` is a value-position marker: `DepFactory[Doc, get_doc]` is a `Dep[Doc]`,
# not a `Doc` (see 2.12 in docs/design-review.md)
static_assert(is_assignable_to(TypeOf[DocDep], Dep[Doc]))
static_assert(is_assignable_to(TypeOf[RoleDep], Dep[str]))

# ... and it is typed, so a marker for one resource is not a marker for another
static_assert(not is_assignable_to(TypeOf[DocDep], Dep[Other]))
static_assert(not is_assignable_to(TypeOf[RoleDep], Dep[Doc]))

# `Resource[R]` admits both accepted forms - the marker and the plain loader
static_assert(is_assignable_to(Dep[Doc], Resource[Doc]))
static_assert(is_assignable_to(TypeOf[DocDep], Resource[Doc]))
static_assert(is_assignable_to(CallableTypeOf[get_doc], Resource[Doc]))

static_assert(not is_assignable_to(Dep[str], Resource[Doc]))
static_assert(not is_assignable_to(CallableTypeOf[get_doc], Resource[Other]))

# a resource marker is not the resource itself
static_assert(not is_assignable_to(Dep[Doc], Doc))
static_assert(not is_assignable_to(TypeOf[Doc()], Resource[Doc]))

# `Resolved[R]` is the same marker in annotation position - what a check receives is the `R`,
# so the two are exact opposites of one another and neither stands in for the other
static_assert(is_equivalent_to(Resolved[Doc], Doc))
static_assert(not is_assignable_to(Dep[Doc], Resolved[Doc]))
static_assert(not is_assignable_to(TypeOf[DocDep], Resolved[Doc]))
static_assert(not is_assignable_to(Resolved[Doc], Dep[Doc]))
static_assert(not is_assignable_to(Resolved[Doc], Resource[Doc]))

from collections.abc import Generator
from typing import Any, ClassVar

from fastapi_has_permissions import Permission, Policy, Requires, Resource
from fastapi_has_permissions._requires import RequiresDepends

from .deps import (
    Allow,
    Doc,
    DocDep,
    DocPolicy,
    RoleDep,
    TypeOf,
    get_doc,
    is_assignable_to,
    is_equivalent_to,
    is_subtype_of,
    static_assert,
)

# the action slots are plain permissions, whatever the policy's resource is
static_assert(is_equivalent_to(TypeOf[DocPolicy.read], Permission))
static_assert(is_equivalent_to(TypeOf[Policy.default], Permission))
static_assert(is_subtype_of(TypeOf[DocPolicy()], Policy[Doc]))

# `__resource__` is a `ClassVar[Resource[Any]]` - a `ClassVar` may not reference the
# policy's type variable, so the resource type is tied to the policy by `bind`/`Requires`
static_assert(is_equivalent_to(TypeOf[Policy.__resource__], Resource[Any]))
static_assert(is_assignable_to(TypeOf[DocPolicy.__resource__], Resource[Any]))


class _MarkerResource(Policy[Doc]):
    __resource__ = DocDep


class _CallableResource(Policy[Doc]):
    __resource__ = get_doc


# `bind` keeps the policy's own type, so a subclass binds to a subclass
_Bound = DocPolicy.bind(DocDep)

static_assert(is_equivalent_to(TypeOf[_Bound], type[DocPolicy]))
static_assert(is_equivalent_to(TypeOf[_Bound()], DocPolicy))
static_assert(is_equivalent_to(TypeOf[DocPolicy.bind(get_doc)], type[DocPolicy]))

# ... and a bound policy still carries its resource type through `Requires`
static_assert(is_equivalent_to(TypeOf[Requires(_Bound())], RequiresDepends[Doc]))


class _Unparametrized(Policy):
    read: ClassVar[Permission] = Allow()


async def _get_nothing() -> None:
    return None


# `TResource` defaults to `None`, so an unparametrized policy binds to a resourceless loader
static_assert(is_equivalent_to(TypeOf[_Unparametrized.bind(_get_nothing)], type[_Unparametrized]))
static_assert(is_equivalent_to(TypeOf[Requires(_Unparametrized())], RequiresDepends[None]))


def _dispatch(policy: DocPolicy) -> None:
    static_assert(is_equivalent_to(TypeOf[policy.__get_permissions_for_method__("GET")], Generator[Permission]))


def _negatives() -> None:
    # the bound resource must load what the policy is parametrized with
    DocPolicy.bind(RoleDep)  # type: ignore[ty:invalid-argument-type]
    _Unparametrized.bind(DocDep)  # type: ignore[ty:invalid-argument-type]

    # an action slot holds a permission, not a policy or a bare callable
    class _BadAction(Policy[Doc]):
        read: ClassVar[Permission] = DocPolicy()  # type: ignore[ty:invalid-assignment]

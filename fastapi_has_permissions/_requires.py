from __future__ import annotations

from collections.abc import Callable, Collection, Iterable
from typing import Any, cast, overload

from fastapi.params import Depends
from fastapi_injected import MakeDataclass, is_dep, resolve, unwrap_dep_dependency

from ._permissions import Permission
from ._policy import Policy
from .types import Resource


class RequiresResolver[R](MakeDataclass):
    resource_dep: Resource[R]
    requirement: Permission | Policy[R]

    def __lazy_depends__(self, methods: Collection[str], /) -> Iterable[Depends]:
        # the loader reads the request as well, so what it needs is the caller's to supply
        resource = unwrap_dep_dependency(self.resource_dep) if is_dep(self.resource_dep) else self.resource_dep

        yield Depends(cast("Callable[..., Any]", resource))
        yield from self.requirement.__lazy_depends__(methods)

    async def __call__(self) -> R:
        await resolve(self.requirement)

        return cast("R", await resolve(self.resource_dep))


class RequiresDepends[R](Depends):
    dependency: RequiresResolver[R]

    def __init__(self, dependency: RequiresResolver[R], /, *, use_cache: bool = True) -> None:
        super().__init__(dependency, use_cache=use_cache)


@overload
def Requires[R](
    policy: Policy[R],
    permission: Permission | None = None,
    /,
    *,
    use_cache: bool = True,
) -> RequiresDepends[R]:
    pass


@overload
def Requires[R](
    resource_dep: Resource[R],
    policy: Policy[R] | Permission,
    /,
    *,
    use_cache: bool = True,
) -> RequiresDepends[R]:
    pass


def Requires[R](  # noqa: N802
    __arg0: Resource[R] | Policy[R],
    __arg1: Permission | Policy[R] | None = None,
    /,
    *,
    use_cache: bool = True,
) -> RequiresDepends[R]:
    if isinstance(__arg0, type) and issubclass(__arg0, Policy):
        msg = f"Requires() takes a policy instance, not the class - use {__arg0.__name__}()"
        raise TypeError(msg)

    if isinstance(__arg0, Policy):
        policy, permission = __arg0, __arg1

        return RequiresDepends(
            RequiresResolver(
                # the policy's own resource is only known as `Resource[Any]` - see `Policy`
                cast("Resource[R]", type(policy).__resource__),
                policy if permission is None else permission,
            ),
            use_cache=use_cache,
        )

    resource_dep, requirement = __arg0, __arg1

    if requirement is None:
        msg = "Requires() needs a permission or a policy alongside an explicit resource dependency"
        raise TypeError(msg)

    return RequiresDepends(
        RequiresResolver(resource_dep, requirement),
        use_cache=use_cache,
    )


__all__ = [
    "Requires",
    "RequiresDepends",
    "RequiresResolver",
]

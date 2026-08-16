from __future__ import annotations

from typing import cast, overload

from fastapi.params import Depends
from fastapi_injected import resolve

from ._bases import ForceDataclass
from ._permissions import Permission
from ._policy import Policy
from ._resolvers import as_validation_error
from .types import Resource


class RequiresResolver[R](ForceDataclass):
    resource_dep: Resource[R]
    requirement: Permission | Policy[R]

    async def __call__(self) -> R:
        await resolve(self.requirement)

        # the loader reads the request too, so a parameter it is missing is the caller's
        # mistake - a 422, exactly as it would be on the handler itself
        with as_validation_error():
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

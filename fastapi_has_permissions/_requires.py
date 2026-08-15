from __future__ import annotations

from typing import cast, overload

from fastapi.params import Depends
from fastapi_injected import resolve

from ._bases import ForceDataclass
from ._permissions import Permission
from ._policy import Policy
from .types import Dep


class RequiresResolver[R](ForceDataclass):
    resource_dep: Dep[R]
    requirement: Permission | Policy[R]

    async def __call__(self) -> R:
        await resolve(self.requirement)

        return cast(
            R,
            await resolve(self.resource_dep),  # type: ignore[ty:invalid-type-form]
        )


@overload
def Requires[R](
    policy: Policy[R],
    permission: Permission | None = None,
    /,
    *,
    use_cache: bool = True,
) -> Depends:
    pass


@overload
def Requires[R](
    resource_dep: Dep[R],
    policy: Policy[R] | Permission,
    /,
    *,
    use_cache: bool = True,
) -> Depends:
    pass


def Requires[R](  # noqa: N802
    __arg0: Dep[R] | Policy[R],
    __arg1: Permission | Policy[R] | None = None,
    /,
    *,
    use_cache: bool = True,
) -> Depends:
    if isinstance(__arg0, type) and issubclass(__arg0, Policy):
        msg = f"Requires() takes a policy instance, not the class - use {__arg0.__name__}()"
        raise TypeError(msg)

    if isinstance(__arg0, Policy):
        policy, permission = __arg0, __arg1

        return Depends(
            RequiresResolver(
                cast("Dep[R]", type(policy).__resource__),
                policy if permission is None else permission,
            ),
            use_cache=use_cache,
        )

    resource_dep, requirement = __arg0, __arg1

    if requirement is None:
        msg = "Requires() needs a permission or a policy alongside an explicit resource dependency"
        raise TypeError(msg)

    return Depends(
        RequiresResolver(cast("Dep[R]", resource_dep), requirement),
        use_cache=use_cache,
    )


__all__ = [
    "Requires",
    "RequiresResolver",
]

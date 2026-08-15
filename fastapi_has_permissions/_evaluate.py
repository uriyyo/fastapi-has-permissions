from typing import Annotated

from fastapi import Depends

from ._bases import ForceDataclass, IdentityHashMixin
from ._permissions import Permission
from ._resolvers import lazy_check_permission
from ._results import CheckResult, Failed, is_skipped, is_successful


async def evaluate(permission: Permission, /) -> CheckResult:
    return await lazy_check_permission(permission)


class PermissionEvaluator(ForceDataclass, IdentityHashMixin):
    async def __call__(self, permission: Permission, /) -> CheckResult:
        return await evaluate(permission)

    async def check(self, permission: Permission, /) -> bool:
        return is_successful(await self(permission))

    async def require(self, permission: Permission, /) -> CheckResult:
        result = await self(permission)

        if isinstance(result, Failed):
            permission.raise_http_exception(result.reason, result.status_code, result.code, result.headers)

        if is_skipped(result):
            permission.raise_http_exception()

        return result


async def _create_evaluator() -> PermissionEvaluator:
    return PermissionEvaluator()


type Evaluate = Annotated[
    PermissionEvaluator,
    Depends(_create_evaluator),
]


__all__ = [
    "Evaluate",
    "PermissionEvaluator",
    "evaluate",
]

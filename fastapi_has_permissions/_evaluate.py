from typing import TYPE_CHECKING, Annotated, Any, ClassVar, final

from fastapi import Depends

from ._bases import ForceDataclass
from ._permissions import Permission, PermissionWrapper
from ._resolvers import lazy_check_permission
from ._results import CheckResult, Failed, is_skipped, is_successful


async def evaluate(permission: Permission, /) -> CheckResult:
    return await lazy_check_permission(permission)


class PermissionEvaluator(ForceDataclass):
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


@final
class _Evaluated(PermissionWrapper):
    __auto_error__: ClassVar[bool] = False


if TYPE_CHECKING:
    from typing import Annotated as Eval
else:

    class Eval:
        def __class_getitem__(cls, item: Any) -> Any:
            match item:
                case (tp, Permission() as permission):
                    return Annotated[tp, Depends(_Evaluated(permission))]
                case _:
                    msg = f"Invalid item: {item!r}"
                    raise TypeError(msg)


__all__ = [
    "Eval",
    "Evaluate",
    "PermissionEvaluator",
    "evaluate",
]

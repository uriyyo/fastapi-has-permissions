from collections.abc import AsyncIterator, Iterable
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import field, replace
from typing import TYPE_CHECKING, Annotated, Any, ClassVar, Self, final

from fastapi import Depends, Request
from fastapi_injected import push_inject_scope, push_overrides
from fastapi_injected.overrides import Overrides
from fastapi_injected.scope import current_inject_scope

from ._bases import ForceDataclass
from ._permissions import Permission, PermissionWrapper
from ._resolvers import lazy_check_permission
from ._results import CheckResult, Failed, as_failed, is_successful, to_failed
from .types import ExceptionFactory, PermissionFactory


class PermissionEvaluator(ForceDataclass):
    on_failure: ExceptionFactory | None = field(default=None, kw_only=True)

    async def __call__(self, permission: Permission, /) -> CheckResult:
        return await lazy_check_permission(permission)

    async def check(self, permission: Permission, /) -> bool:
        return is_successful(await self(permission))

    async def require(self, permission: Permission, /) -> CheckResult:
        result = await self(permission)

        if is_successful(result):
            return result

        failed = as_failed(result, to_failed(permission))
        raise self.__to_exception__(permission, failed)

    async def filter[T](self, items: Iterable[T], permission: PermissionFactory[T], /) -> list[T]:
        return [item for item in items if await self.check(permission(item))]

    @asynccontextmanager
    async def scope(
        self,
        overrides: Overrides | None = None,
        /,
        *,
        request: Request | None = None,
        on_failure: ExceptionFactory | None = None,
    ) -> AsyncIterator[Self]:
        # inherit the surrounding request so request-bound dependencies keep resolving,
        # while the fresh scope gives the overrides a cache of their own
        if request is None and (current := current_inject_scope()) is not None:
            request = current.request

        async with AsyncExitStack() as stack:
            await stack.enter_async_context(push_inject_scope(request=request))

            if overrides is not None:
                stack.enter_context(push_overrides(overrides))

            yield replace(self, on_failure=on_failure or self.on_failure)

    def __to_exception__(self, permission: Permission, failed: Failed, /) -> Exception:
        if self.on_failure is not None:
            return self.on_failure(permission, failed)

        return permission.build_error(failed.reason, failed.status_code, failed.code, failed.headers, failed.source)


evaluate = PermissionEvaluator()


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

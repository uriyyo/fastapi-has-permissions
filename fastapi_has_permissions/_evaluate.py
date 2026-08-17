from collections.abc import AsyncIterator, Iterable
from contextlib import asynccontextmanager
from dataclasses import field, replace
from typing import TYPE_CHECKING, Annotated, Any, ClassVar, Self, final

from fastapi import Depends, FastAPI, Request
from fastapi_injected import InjectScope, MakeDataclass, Overrides, push_inject_scope

from ._errors import SyntheticScopeError
from ._permissions import Permission, PermissionWrapper
from ._resolvers import lazy_check_permission
from ._results import CheckResult, Failed, as_failed, is_successful, to_failed
from .types import ExceptionFactory, PermissionFactory


class PermissionEvaluator(MakeDataclass):
    on_failure: ExceptionFactory | None = field(default=None, kw_only=True)
    # refuse to decide against a request that never existed - a dependency that tolerates
    # a missing actor would otherwise report an ordinary denial, and nothing would say why
    strict: bool = field(default=False, kw_only=True)

    async def __call__(self, permission: Permission, /) -> CheckResult:
        if self.strict:
            self.__check_scope__()

        return await lazy_check_permission(permission)

    def __check_scope__(self) -> None:
        scope = InjectScope.current()

        if scope is None or scope.synthetic:
            raise SyntheticScopeError

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
        app: FastAPI | None = None,
        on_failure: ExceptionFactory | None = None,
        strict: bool | None = None,
    ) -> AsyncIterator[Self]:
        evaluator = replace(
            self,
            on_failure=on_failure or self.on_failure,
            strict=self.strict if strict is None else strict,
        )

        async with push_inject_scope(overrides, request=request, app=app):
            yield evaluator

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

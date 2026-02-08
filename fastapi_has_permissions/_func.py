import inspect
from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from typing import Any, TypeVar, overload

from fastapi.dependencies.utils import get_typed_signature

from ._permissions import Permission
from ._results import CheckResult
from .types import AsyncFunc

TAsyncFunc = TypeVar("TAsyncFunc", bound=AsyncFunc)


@dataclass
class FuncPermission(Permission):
    func: AsyncFunc

    def __check_signature__(self) -> inspect.Signature:
        return get_typed_signature(self.func)

    async def check_permissions(self, *args: Any, **kwargs: Any) -> CheckResult:
        return await self.func(*args, **kwargs)


@overload
def permission(arg: TAsyncFunc, /) -> FuncPermission:
    pass


@overload
def permission(
    arg: None = None,
    /,
    *,
    message: str | None = None,
    status_code: int | None = None,
) -> Callable[[TAsyncFunc], FuncPermission]:
    pass


def permission(
    arg: TAsyncFunc | None = None,
    /,
    *,
    message: str | None = None,
    status_code: int | None = None,
) -> Any:
    if arg is None:
        return partial(permission, message=message, status_code=status_code)

    return FuncPermission(func=arg, message=message, status_code=status_code)


__all__ = [
    "permission",
]

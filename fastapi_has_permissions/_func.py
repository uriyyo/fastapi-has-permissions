import inspect
from collections.abc import Callable, Iterable, Sequence
from functools import partial
from typing import Any, overload

from fastapi.dependencies.utils import get_typed_signature
from fastapi_injected import is_dep, unwrap_dep_tp

from ._deps_args import get_signature_with_deps
from ._permissions import Permission
from ._results import CheckResult
from .types import AsyncFunc, Dep


def _func_deps(func: AsyncFunc, /) -> Iterable[Dep]:
    sign = get_typed_signature(func)
    deps_ended = False

    for param in sign.parameters.values():
        if is_dep(param.annotation):
            if deps_ended:
                msg = f"All dependencies must be defined before non-dependencies in {func!r}"
                raise TypeError(msg)

            yield unwrap_dep_tp(param.annotation)
        else:
            deps_ended = True


class FuncPermission(Permission):
    func: AsyncFunc
    deps: Sequence[Dep] = ()

    def __deps__(self) -> Iterable[Dep]:
        if len(self.deps) != len([*_func_deps(self.func)]):
            msg = (
                f"Explicitly defined dependencies {self.deps!r} do not match the "
                f"dependencies defined in the function signature of {self.func!r}"
            )
            raise TypeError(msg)

        yield from self.deps

    def __check_signature__(self) -> inspect.Signature:
        return get_signature_with_deps(self.func, [*self.__deps__()])

    async def check_permissions(self, *args: Any, **kwargs: Any) -> CheckResult:
        return await self.func(*args, **kwargs)


@overload
def permission[TAsyncFunc: AsyncFunc](arg: TAsyncFunc, /) -> Callable[..., FuncPermission]:
    pass


@overload
def permission[TAsyncFunc: AsyncFunc](
    arg: None = None,
    /,
    *,
    message: str | None = None,
    status_code: int | None = None,
    code: str | None = None,
    headers: dict[str, str] | None = None,
) -> Callable[[TAsyncFunc], Callable[..., FuncPermission]]:
    pass


def permission[TAsyncFunc: AsyncFunc](
    arg: TAsyncFunc | None = None,
    /,
    *,
    message: str | None = None,
    status_code: int | None = None,
    code: str | None = None,
    headers: dict[str, str] | None = None,
) -> Any:
    if arg is None:
        return partial(permission, message=message, status_code=status_code, code=code, headers=headers)

    return _permission_factory(arg, message=message, status_code=status_code, code=code, headers=headers)


def _permission_factory[TAsyncFunc: AsyncFunc](
    arg: TAsyncFunc,
    message: str | None = None,
    status_code: int | None = None,
    code: str | None = None,
    headers: dict[str, str] | None = None,
) -> Callable[..., FuncPermission]:
    def _factory(*deps: Dep) -> FuncPermission:
        return FuncPermission(
            func=arg,
            deps=deps,
            message=message,
            status_code=status_code,
            code=code,
            headers=headers,
        )

    return _factory


__all__ = [
    "permission",
]

import inspect
from dataclasses import dataclass, field
from functools import partial
from typing import Protocol, TypeVar, cast, overload

from fastapi.dependencies.utils import get_typed_signature

from ._bases import ForceDataclass
from ._permissions import Permission, PermissionWrapper
from ._resolvers import BaseResolvedPermission, PermissionResolver, resolve_permission
from ._results import CheckResult, Skipped, SkipPermissionCheck
from .types import Exceptions


class LazyResolvedPermission(ForceDataclass, BaseResolvedPermission):
    permission: Permission
    skip_on_exc: Exceptions = ()

    async def check_permissions(self) -> CheckResult:
        try:
            return await self._check_permissions()
        except SkipPermissionCheck as e:
            return Skipped(reason=e.reason)
        except self.skip_on_exc:
            return Skipped()

    async def _check_permissions(self) -> CheckResult:
        final_permission = await resolve_permission(self.permission)

        return await final_permission.check_permissions()


class LazyPermissionResolver(PermissionResolver):
    skip_on_exc: Exceptions = field(default=(), kw_only=True)

    def __get_signature__(self) -> inspect.Signature:
        return get_typed_signature(self.__call__)

    async def __call__(self) -> BaseResolvedPermission:
        return LazyResolvedPermission(
            permission=self.permission,
            skip_on_exc=self.skip_on_exc,
        )


@dataclass
class _HasSkipOnExc:
    skip_on_exc: Exceptions = field(default=(), kw_only=True)


class LazyPermission(_HasSkipOnExc, Permission):
    def __to_resolver__(self) -> LazyPermissionResolver:
        return LazyPermissionResolver(self, skip_on_exc=self.skip_on_exc)


class LazyPermissionWrapper(_HasSkipOnExc, PermissionWrapper):
    def __to_resolver__(self) -> LazyPermissionResolver:
        return LazyPermissionResolver(self.permission, skip_on_exc=self.skip_on_exc)


TCls = TypeVar("TCls", bound=type[Permission])
TPermission = TypeVar("TPermission", bound=Permission)


class _LazyDecorator(Protocol):
    @overload
    def __call__(self, arg: TCls, /) -> TCls:
        pass

    @overload
    def __call__(self, arg: TPermission, /) -> LazyPermissionWrapper:
        pass


@overload
def lazy(
    arg: None = None,
    /,
    *,
    skip_on_exc: Exceptions | None = None,
) -> _LazyDecorator:
    pass


@overload
def lazy[TCls: type[Permission]](cls: TCls, /) -> TCls:
    pass


@overload
def lazy[TPermission: Permission](
    permission: TPermission,
    /,
    *,
    skip_on_exc: Exceptions | None = None,
) -> LazyPermissionWrapper:
    pass


def lazy(
    arg: type[Permission] | Permission | None = None,
    /,
    *,
    skip_on_exc: Exceptions | None = None,
) -> type[Permission] | LazyPermissionWrapper | _LazyDecorator:
    if arg is None:
        return cast(
            "_LazyDecorator",
            partial(lazy, skip_on_exc=skip_on_exc),
        )

    if isinstance(arg, type):
        if issubclass(arg, LazyPermission):
            raise TypeError("Cannot apply @lazy to a subclass of LazyPermission")

        ns = {}
        if skip_on_exc is not None:
            ns["skip_on_exc"] = skip_on_exc

        return type(f"Lazy{arg.__name__}", (LazyPermission, arg), ns)

    return LazyPermissionWrapper(
        permission=arg,
        skip_on_exc=skip_on_exc or (),
    )


__all__ = [
    "LazyPermission",
    "LazyPermissionResolver",
    "lazy",
]

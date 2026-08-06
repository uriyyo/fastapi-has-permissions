import inspect
from dataclasses import dataclass, field
from functools import cached_property, partial
from typing import Annotated, Any, Protocol, TypeVar, cast, overload

from fastapi import Depends, Request
from fastapi.dependencies.utils import get_typed_signature
from fastapi.exceptions import RequestValidationError
from fastapi_injected import init_inject_scope, resolve
from fastapi_injected.deps import set_inject_dependency_override_provider

from ._bases import ForceDataclass
from ._permissions import Permission, PermissionWrapper
from ._resolvers import BaseResolvedPermission, PermissionResolver
from ._results import CheckResult, Skipped, SkipPermissionCheck
from .types import Exceptions


def _to_validation_error(exc: ValueError, /) -> RequestValidationError | None:
    # fastapi-injected reports unresolvable dependencies as ValueError(errors),
    # but this library exposes them as RequestValidationError (used by skip_on_exc)
    match exc.args:
        case ([dict(), *_] as errors,):
            return RequestValidationError(errors)
        case _:
            return None


class LazyResolvedPermission(ForceDataclass, BaseResolvedPermission):
    permission: Permission
    skip_on_exc: Exceptions = ()

    @cached_property
    def _eager_resolver(self) -> PermissionResolver:
        return PermissionResolver(self.permission)

    async def check_permissions(self) -> CheckResult:
        try:
            return await self._check_permissions()
        except SkipPermissionCheck as e:
            return Skipped(reason=e.reason)
        except self.skip_on_exc:
            return Skipped()

    async def _check_permissions(self) -> CheckResult:
        try:
            # resolve the permission dependencies against the ambient inject scope,
            # which is bound to the current request by LazyPermissionResolver
            final_permission = await resolve(cast("Any", self._eager_resolver))
        except ValueError as exc:
            if (validation_error := _to_validation_error(exc)) is None:
                raise

            raise validation_error from exc

        return await final_permission.check_permissions()


class LazyPermissionResolver(PermissionResolver):
    skip_on_exc: Exceptions = field(default=(), kw_only=True)

    def __get_signature__(self) -> inspect.Signature:
        return get_typed_signature(self.__call__)

    async def __call__(
        self,
        request: Request,
        _scope: Annotated[None, Depends(init_inject_scope)],
    ) -> BaseResolvedPermission:
        route = request.scope["route"]
        set_inject_dependency_override_provider(route.dependency_overrides_provider)

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
def lazy(cls: TCls, /) -> TCls:
    pass


@overload
def lazy(
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

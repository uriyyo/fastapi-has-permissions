from __future__ import annotations

import inspect
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

from fastapi.exceptions import RequestValidationError
from fastapi_injected import resolve
from fastapi_injected.deps import HasDependsHook

from ._bases import ForceDataclass, IdentityHashMixin, SignatureOverride
from ._deps_args import remap_deps_args
from ._results import CheckResult, Skipped, SkipPermissionCheck, call_permissions_check
from .types import Args, Kwargs

if TYPE_CHECKING:
    from ._permissions import Permission


class BaseResolvedPermission(ABC, IdentityHashMixin):
    @abstractmethod
    async def check_permissions(self) -> CheckResult:
        pass


class ResolvedPermission(ForceDataclass, BaseResolvedPermission):
    permission: Permission
    args: Args
    kwargs: Kwargs

    async def check_permissions(self) -> CheckResult:
        return await call_permissions_check(self.permission, *self.args, **self.kwargs)


class PermissionResolver(ForceDataclass, IdentityHashMixin, SignatureOverride):
    permission: Permission

    def __get_signature__(self) -> inspect.Signature:
        return self.permission.__check_signature__()

    @remap_deps_args
    async def __call__(self, *args: Any, **kwargs: Any) -> BaseResolvedPermission:
        return ResolvedPermission(self.permission, args, kwargs)


class Resolvable(Protocol):
    @abstractmethod
    def __to_resolver__(self) -> PermissionResolver:
        pass


def to_validation_error(exc: ValueError, /) -> RequestValidationError | None:
    match exc.args:
        case ([dict(), *_] as errors,):
            return RequestValidationError(errors)
        case _:
            return None


@dataclass(frozen=True)
class _Adapter(HasDependsHook):
    resolver: PermissionResolver
    permission: Permission

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self.resolver(*args, **kwargs)

    def __get_depends__(self) -> Any:
        return self.permission.__resolver_to_depends__(self.resolver)


async def resolve_permission(permission: Permission, /) -> BaseResolvedPermission:
    resolver = PermissionResolver(permission)
    try:
        return await resolve(_Adapter(resolver, permission))
    except ValueError as exc:
        if validation_error := to_validation_error(exc):
            raise validation_error from exc

        raise


async def lazy_check_permission(permission: Permission, /) -> CheckResult:
    try:
        resolved = await resolve_permission(permission)
    except SkipPermissionCheck as exc:
        return Skipped(reason=exc.reason)

    return await resolved.check_permissions()


__all__ = [
    "BaseResolvedPermission",
    "PermissionResolver",
    "Resolvable",
    "ResolvedPermission",
    "lazy_check_permission",
    "resolve_permission",
    "to_validation_error",
]

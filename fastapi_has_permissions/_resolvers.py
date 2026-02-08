from __future__ import annotations

import inspect
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

from ._bases import IdentityHashMixin, SignatureOverride
from ._deps_args import remap_deps_args
from ._results import CheckResult, call_permissions_check
from .types import Args, Kwargs

if TYPE_CHECKING:
    from ._permissions import Permission


class BaseResolvedPermission(ABC, IdentityHashMixin):
    @abstractmethod
    async def check_permissions(self) -> CheckResult:
        pass


@dataclass
class ResolvedPermission(BaseResolvedPermission):
    permission: Permission
    args: Args
    kwargs: Kwargs

    async def check_permissions(self) -> CheckResult:
        return await call_permissions_check(self.permission, *self.args, **self.kwargs)


@dataclass
class PermissionResolver(IdentityHashMixin, SignatureOverride):
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


__all__ = [
    "BaseResolvedPermission",
    "PermissionResolver",
    "Resolvable",
    "ResolvedPermission",
]

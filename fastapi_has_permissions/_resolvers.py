from __future__ import annotations

import inspect
from abc import abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol, TypeAlias

from ._bases import IdentityHashMixin, SignatureOverride
from ._deps_args import remap_deps_args
from ._results import CheckResult, Skipped, call_permissions_check
from .types import Args, Kwargs

if TYPE_CHECKING:
    from ._permissions import Permission


@dataclass
class ResolvedPermission(IdentityHashMixin):
    permission: Permission
    args: Args
    kwargs: Kwargs

    async def check_permissions(self) -> CheckResult:
        return await call_permissions_check(self.permission, *self.args, **self.kwargs)


@dataclass
class ResolvedToSkipped(IdentityHashMixin):
    reason: str | None = None

    async def check_permissions(self) -> Skipped:
        return Skipped(reason=self.reason)


ResolvedResult: TypeAlias = ResolvedPermission | ResolvedToSkipped


@dataclass
class PermissionResolver(IdentityHashMixin, SignatureOverride):
    permission: Permission

    def __get_signature__(self) -> inspect.Signature:
        return self.permission.__check_signature__()

    @remap_deps_args
    async def __call__(self, *args: Any, **kwargs: Any) -> ResolvedResult:
        return ResolvedPermission(self.permission, args, kwargs)


class Resolvable(Protocol):
    @abstractmethod
    def __to_resolver__(self) -> PermissionResolver:
        pass


__all__ = [
    "PermissionResolver",
    "Resolvable",
    "ResolvedPermission",
    "ResolvedResult",
    "ResolvedToSkipped",
]

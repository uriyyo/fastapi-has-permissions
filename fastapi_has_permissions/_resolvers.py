from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi_injected import MakeDataclass, remap_dep_args, resolve

from ._results import CheckResult, Skipped, SkipPermissionCheck, call_permissions_check
from ._security import as_hashable_security

if TYPE_CHECKING:
    from ._permissions import Permission


class PermissionResolver(MakeDataclass):
    permission: Permission

    def __post_init__(self) -> None:
        super().__post_init__()
        self.__signature__ = self.permission.__check_signature__()

    def __get_depends__(self) -> Any:
        return as_hashable_security(self.permission.__resolver_to_depends__(self))

    @remap_dep_args
    async def __call__(self, *args: Any, **kwargs: Any) -> CheckResult:
        return await call_permissions_check(self.permission, *args, **kwargs)


async def lazy_check_permission(permission: Permission, /) -> CheckResult:
    try:
        return await resolve(PermissionResolver(permission))
    except SkipPermissionCheck as exc:
        return Skipped(reason=exc.reason)


__all__ = [
    "PermissionResolver",
    "lazy_check_permission",
]

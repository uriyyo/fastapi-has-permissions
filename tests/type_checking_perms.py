from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi_has_permissions import Permission

if TYPE_CHECKING:
    from fastapi_has_permissions import Dep

    type RoleDep = Dep[str]


class HasRoleTypeCheckingDep(Permission):
    role_dep: RoleDep

    async def check_permissions(self, role: str, /) -> bool:
        return role == "admin"


__all__ = [
    "HasRoleTypeCheckingDep",
]

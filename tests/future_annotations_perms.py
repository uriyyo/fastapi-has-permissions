from __future__ import annotations

from fastapi_has_permissions import Dep, Permission


class HasRoleFutureAnnotations(Permission):
    role_dep: Dep[str]

    async def check_permissions(self, role: str, /) -> bool:
        return role == "admin"


__all__ = [
    "HasRoleFutureAnnotations",
]

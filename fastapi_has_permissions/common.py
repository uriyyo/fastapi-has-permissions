from collections.abc import Iterable
from typing import Any

from fastapi import Security
from fastapi.security import SecurityScopes

from ._permissions import Permission, PermissionWrapper
from ._resolvers import PermissionResolver
from .types import Dep


def _to_frozenset(value: Iterable[str], /) -> frozenset[str]:
    match value:
        case str():
            return frozenset((value,))
        case _:
            return frozenset(value)


class IsAuthenticated(Permission):
    authentication_dep: Dep

    async def check_permissions(self, is_authenticated: bool, /) -> bool:  # noqa: FBT001
        return is_authenticated


class HasScope(Permission):
    scope_dep: Dep
    scopes: Iterable[str]

    def __post_init__(self) -> None:
        self.scopes = _to_frozenset(self.scopes)
        super().__post_init__()

    def __resolver_to_depends__(self, resolver: PermissionResolver) -> Any:
        return Security(resolver, scopes=[*self.scopes])

    async def check_permissions(self, current_scopes: Iterable[str], /, security_scopes: SecurityScopes) -> bool:
        return all(required_scope in current_scopes for required_scope in security_scopes.scopes)


class HasRole(Permission):
    role_dep: Dep
    roles: Iterable[str]

    def __post_init__(self) -> None:
        self.roles = _to_frozenset(self.roles)
        super().__post_init__()

    async def check_permissions(self, current_role: str, /) -> bool:
        return current_role in self.roles


def no_auto_error(permission: Permission) -> PermissionWrapper:
    return PermissionWrapper(permission, auto_error=False)


__all__ = [
    "HasRole",
    "HasScope",
    "IsAuthenticated",
    "no_auto_error",
]

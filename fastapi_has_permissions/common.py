from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from fastapi import Security
from fastapi.security import SecurityScopes

from ._permissions import Permission
from ._resolvers import PermissionResolver
from .types import Dep


@dataclass
class IsAuthenticated(Permission):
    authentication_dep: Dep

    async def check_permissions(self, is_authenticated: bool, /) -> bool:  # noqa: FBT001
        return is_authenticated


@dataclass
class HasScope(Permission):
    scope_dep: Dep
    scopes: Iterable[str]

    def __resolver_to_depends__(self, resolver: PermissionResolver) -> Any:
        return Security(resolver, scopes=[*self.scopes])

    async def check_permissions(self, current_scopes: Iterable[str], /, security_scopes: SecurityScopes) -> bool:
        return all(required_scope in current_scopes for required_scope in security_scopes.scopes)


@dataclass
class HasRole(Permission):
    role_dep: Dep
    roles: Iterable[str]

    async def check_permissions(self, current_role: str, /) -> bool:
        return current_role in self.roles


__all__ = [
    "HasRole",
    "HasScope",
    "IsAuthenticated",
]

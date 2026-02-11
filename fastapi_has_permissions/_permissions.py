from __future__ import annotations

import inspect
from abc import ABC, abstractmethod
from collections.abc import Iterable, Sequence
from dataclasses import field, fields
from typing import TYPE_CHECKING, Annotated, Any, ClassVar, final

from fastapi import Depends
from typing_extensions import Self

from ._bases import ForceDataclass, IdentityHashMixin, SignatureOverride
from ._dep import is_dep
from ._deps_args import (
    get_dep_arg_name,
    get_signature_with_deps,
    remap_deps_args,
    signature_with_params,
)
from ._errors import HTTPExcRaiser
from ._resolvers import PermissionResolver, Resolvable, ResolvedPermission
from ._results import CheckResult, Failed, Skipped, is_skipped
from .types import AsyncFunc, Dep


class BasePermission(ABC):  # noqa: B024
    if TYPE_CHECKING:

        @property
        @abstractmethod
        def check_permissions(self) -> AsyncFunc[CheckResult]:
            pass
    else:

        @abstractmethod
        async def check_permissions(self, *args: Any, **kwargs: Any) -> CheckResult:
            pass


class Permission(
    ForceDataclass,
    BasePermission,
    HTTPExcRaiser,
    Resolvable,
    SignatureOverride,
    IdentityHashMixin,
    ABC,
):
    auto_error: bool = field(default=True, kw_only=True)

    def __deps__(self) -> Iterable[Dep]:
        for dfield in fields(self):
            if is_dep(dfield.type):
                yield getattr(self, dfield.name)

    def __get_signature__(self) -> inspect.Signature:
        return signature_with_params([self.__to_sign_param__()])

    def __check_signature__(self) -> inspect.Signature:
        return get_signature_with_deps(self.check_permissions, [*self.__deps__()])

    def __to_sign_param__(self, idx: int = 0, /) -> inspect.Parameter:
        return inspect.Parameter(
            name=get_dep_arg_name(idx),
            kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
            annotation=Annotated[
                PermissionResolver,
                self.__resolver_to_depends__(self.__to_resolver__()),
            ],
        )

    def __to_resolver__(self) -> PermissionResolver:
        return PermissionResolver(permission=self)

    def __resolver_to_depends__(self, resolver: PermissionResolver) -> Any:
        return Depends(resolver)

    @remap_deps_args
    async def __call__(self, permission: ResolvedPermission) -> CheckResult:
        message: str | None = None
        result: bool

        match ret := await permission.check_permissions():
            case Failed(reason=reason):
                message = reason
                result = False
            case False:
                message = self.get_exc_message()
                result = False
            case _:
                result = True

        if self.auto_error and not result:
            self.raise_http_exception(message)

        return ret

    def __and__(self, other: Permission) -> Permission:
        if not isinstance(other, Permission):
            return NotImplemented

        return AllPermissions([self, other])

    def __or__(self, other: Permission) -> Permission:
        if not isinstance(other, Permission):
            return NotImplemented

        return AnyPermissions([self, other])

    def __invert__(self) -> Permission:
        return NotPermission(self)


class _AllAnyPermissions(Permission):
    permissions: Sequence[Permission]

    def __check_signature__(self) -> inspect.Signature:
        return signature_with_params([permission.__to_sign_param__(i) for i, permission in enumerate(self.permissions)])

    def _merge_permissions(self, other: Permission, cls: type[Self]) -> Self:

        if isinstance(other, cls):
            return cls(permissions=[*self.permissions, *other.permissions])

        return cls(permissions=[*self.permissions, other])


class PermissionWrapper(Permission):
    permission: Permission

    def __check_signature__(self) -> inspect.Signature:
        return signature_with_params([self.permission.__to_sign_param__()])

    async def check_permissions(self, permission: ResolvedPermission) -> CheckResult:
        return await permission.check_permissions()


@final
class AnyPermissions(_AllAnyPermissions):
    default_exc_message: ClassVar[str] = "None of the permissions were satisfied"

    def __or__(self, other: Permission) -> Permission:
        if not isinstance(other, Permission):
            return NotImplemented

        return self._merge_permissions(other, AnyPermissions)

    async def check_permissions(self, *permissions: ResolvedPermission) -> CheckResult:
        only_skips = True

        for permission in permissions:
            result = await permission.check_permissions()

            if is_skipped(result):
                continue

            only_skips = False

            if result:
                return True

        if only_skips:
            return Skipped()

        return False


@final
class AllPermissions(_AllAnyPermissions):
    default_exc_message: ClassVar[str] = "Not all permissions were satisfied"

    def __and__(self, other: Permission) -> Permission:
        if not isinstance(other, Permission):
            return NotImplemented

        return self._merge_permissions(other, AllPermissions)

    async def check_permissions(self, *permissions: ResolvedPermission) -> CheckResult:
        only_skips = False

        for permission in permissions:
            result = await permission.check_permissions()

            if is_skipped(result):
                only_skips = True
                continue

            if not result:
                return False

        if only_skips:
            return Skipped()

        return True


@final
class NotPermission(PermissionWrapper):
    default_exc_message: ClassVar[str] = "The permission was satisfied, but it should not have been"

    async def check_permissions(self, permission: ResolvedPermission) -> CheckResult:
        result = await permission.check_permissions()

        if is_skipped(result):
            return result

        return not result

    def __invert__(self) -> Permission:
        return self.permission


__all__ = [
    "AllPermissions",
    "AnyPermissions",
    "NotPermission",
    "Permission",
    "PermissionWrapper",
]

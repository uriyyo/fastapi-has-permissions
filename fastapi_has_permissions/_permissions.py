from __future__ import annotations

import inspect
from abc import ABC, abstractmethod
from collections.abc import Iterable, Sequence
from dataclasses import field, fields
from typing import TYPE_CHECKING, Annotated, Any, ClassVar, final

from fastapi import Depends
from fastapi.dependencies.utils import get_typed_signature
from fastapi_injected import is_dep

from ._bases import ForceDataclass, IdentityHashMixin, SignatureOverride
from ._deps_args import (
    get_dep_arg_name,
    get_signature_with_deps,
    remap_deps_args,
    signature_with_params,
)
from ._errors import HTTPExcRaiser
from ._resolvers import (
    PermissionResolver,
    Resolvable,
    ResolvedPermission,
    lazy_check_permission,
)
from ._results import CheckResult, Failed, Skipped, is_failed, is_skipped, is_successful
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
        status_code: int | None = None
        code: str | None = None
        headers: dict[str, str] | None = None
        result: bool

        match ret := await permission.check_permissions():
            case Failed(reason=reason, status_code=status_code, code=code, headers=headers):
                message = reason
                result = False
            case Skipped():
                # a skip reaching the top level is an abstention, not an approval - deny it,
                # wrap the permission into `AllowSkipped` to opt into skip-means-allow
                message = self.get_exc_message()
                result = False
            case False:
                message = self.get_exc_message()
                result = False
            case _:
                result = True

        if self.auto_error and not result:
            self.raise_http_exception(message, status_code, code, headers)

        return ret

    def __and__(self, other: Permission) -> Permission:
        if not isinstance(other, Permission):
            return NotImplemented

        return _combine(self, other, AllPermissions)

    def __or__(self, other: Permission) -> Permission:
        if not isinstance(other, Permission):
            return NotImplemented

        return _combine(self, other, AnyPermissions)

    def __invert__(self) -> Permission:
        return NotPermission(self)


class _AllAnyPermissions(Permission):
    permissions: Sequence[Permission]

    def __check_signature__(self) -> inspect.Signature:
        return get_typed_signature(self.check_permissions)


def _flatten(permission: Permission, cls: type[_AllAnyPermissions]) -> list[Permission]:
    # only absorb a same-kind composite that carries no error config of its own,
    # otherwise flattening would silently discard that config
    if isinstance(permission, cls) and permission.auto_error and permission.has_default_error_config():
        return [*permission.permissions]

    return [permission]


def _combine[TComposite: _AllAnyPermissions](
    left: Permission,
    right: Permission,
    cls: type[TComposite],
) -> TComposite:
    return cls(permissions=[*_flatten(left, cls), *_flatten(right, cls)])


class _SinglePermission(Permission):
    permission: Permission


class PermissionWrapper(_SinglePermission):
    def __check_signature__(self) -> inspect.Signature:
        return signature_with_params([self.permission.__to_sign_param__()])

    async def check_permissions(self, permission: ResolvedPermission) -> CheckResult:
        return await permission.check_permissions()


@final
class AllowSkipped(PermissionWrapper):
    async def check_permissions(self, permission: ResolvedPermission) -> CheckResult:
        result = await permission.check_permissions()

        if is_skipped(result):
            return True

        return result


@final
class AnyPermissions(_AllAnyPermissions):
    default_exc_message: ClassVar[str] = "None of the permissions were satisfied"

    async def check_permissions(self) -> CheckResult:
        failures: list[Failed] = []

        for permission in self.permissions:
            result = await lazy_check_permission(permission)

            if is_skipped(result):
                continue

            if is_successful(result):
                return True

            match result:
                case Failed():
                    failures.append(result)
                case _:
                    failures.append(Failed())

        match failures:
            case []:
                return Skipped()
            case [failed]:
                return failed
            case _:
                # reasons are aggregated, but status/code/headers cannot be -
                # the first failing branch wins, so a masking leaf keeps masking
                first = failures[0]
                reasons = [failed.reason for failed in failures if failed.reason]

                return Failed(
                    reason="; ".join(reasons) or None,
                    status_code=first.status_code,
                    code=first.code,
                    headers=first.headers,
                )


@final
class AllPermissions(_AllAnyPermissions):
    default_exc_message: ClassVar[str] = "Not all permissions were satisfied"

    async def check_permissions(self) -> CheckResult:
        skipped = 0

        for permission in self.permissions:
            result = await lazy_check_permission(permission)

            if is_skipped(result):
                skipped += 1
                continue

            if is_failed(result):
                return result

        if self.permissions and skipped == len(self.permissions):
            return Skipped()

        return True


@final
class NotPermission(_SinglePermission):
    default_exc_message: ClassVar[str] = "The permission was satisfied, but it should not have been"

    def __check_signature__(self) -> inspect.Signature:
        return get_typed_signature(self.check_permissions)

    async def check_permissions(self) -> CheckResult:
        result = await lazy_check_permission(self.permission)

        if is_skipped(result):
            return result

        return not result

    def __invert__(self) -> Permission:
        return self.permission


__all__ = [
    "AllPermissions",
    "AllowSkipped",
    "AnyPermissions",
    "NotPermission",
    "Permission",
    "PermissionWrapper",
]

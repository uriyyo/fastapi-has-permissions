from __future__ import annotations

import inspect
from abc import ABC, abstractmethod
from collections.abc import Collection, Iterable, Sequence
from typing import TYPE_CHECKING, Any, ClassVar, final

from fastapi.dependencies.utils import get_typed_signature
from fastapi.params import Depends
from fastapi_injected import is_dep

from ._bases import ForceDataclass
from ._deps_args import get_signature_with_deps
from ._errors import ErrorConfig
from ._resolvers import PermissionResolver, lazy_check_permission
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
    ErrorConfig,
    ABC,
):
    __auto_error__: ClassVar[bool] = True

    def __post_init__(self) -> None:
        pass

    def __deps__(self) -> Iterable[Dep]:
        for param in get_typed_signature(type(self)).parameters.values():
            if is_dep(param.annotation):
                yield getattr(self, param.name)

    def __sub_permissions__(self) -> Iterable[Permission]:
        # the permissions this one delegates to - a leaf has none. Walking these is how
        # the schema pass reaches permissions that only ever resolve at check time.
        return ()

    def __lazy_depends__(self, methods: Collection[str] = (), /) -> Iterable[Depends]:
        yield self.__resolver_to_depends__(PermissionResolver(self))

        for sub in self.__sub_permissions__():
            yield from sub.__lazy_depends__(methods)

    def __check_signature__(self) -> inspect.Signature:
        return get_signature_with_deps(self.check_permissions, [*self.__deps__()])

    def __resolver_to_depends__(self, resolver: PermissionResolver) -> Any:
        return Depends(resolver)

    async def __call__(self) -> CheckResult:
        message: str | None = None
        status_code: int | None = None
        code: str | None = None
        headers: dict[str, str] | None = None
        result: bool

        match ret := await lazy_check_permission(self):
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

        if self.__auto_error__ and not result:
            self.raise_error(message, status_code, code, headers)

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

    def __sub_permissions__(self) -> Iterable[Permission]:
        return self.permissions


def _flatten(permission: Permission, cls: type[_AllAnyPermissions]) -> list[Permission]:
    # only absorb a same-kind composite that carries no error config of its own,
    # otherwise flattening would silently discard that config
    if isinstance(permission, cls) and permission.has_default_error_config():
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

    def __sub_permissions__(self) -> Iterable[Permission]:
        return (self.permission,)


class PermissionWrapper(_SinglePermission):
    async def check_permissions(self) -> CheckResult:
        return await lazy_check_permission(self.permission)


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

    async def check_permissions(self) -> CheckResult:
        result = await lazy_check_permission(self.permission)

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

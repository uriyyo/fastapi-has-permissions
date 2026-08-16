from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING, final

from ._permissions import Permission, PermissionWrapper
from ._resolvers import lazy_check_permission
from ._results import (
    CheckResult,
    Failed,
    Skipped,
    as_failed,
    get_reason,
    is_failed,
    is_skipped,
    is_successful,
    to_failed,
)
from .types import Exceptions

if TYPE_CHECKING:
    from collections.abc import Collection, Iterable

    from fastapi.params import Depends


@final
class WhenPermission(PermissionWrapper):
    guard: Permission

    def __sub_permissions__(self) -> Iterable[Permission]:
        return (self.guard, self.permission)

    async def check_permissions(self) -> CheckResult:
        guard = await lazy_check_permission(self.guard)

        if is_successful(guard):
            return await lazy_check_permission(self.permission)

        return Skipped(reason=get_reason(guard))


def When(guard: Permission, permission: Permission, /) -> WhenPermission:  # noqa: N802
    return WhenPermission(permission, guard=guard)


@final
class Undocumented(PermissionWrapper):
    def __lazy_depends__(self, methods: Collection[str] = (), /) -> Iterable[Depends]:
        return ()


class ResultMapper(PermissionWrapper):
    async def check_permissions(self) -> CheckResult:
        return self.__map_result__(await lazy_check_permission(self.permission))

    @abstractmethod
    def __map_result__(self, result: CheckResult, /) -> CheckResult:
        pass


@final
class AllowSkipped(ResultMapper):
    def __map_result__(self, result: CheckResult, /) -> CheckResult:
        if is_skipped(result):
            return True

        return result


@final
class DenySkipped(ResultMapper):
    def __map_result__(self, result: CheckResult, /) -> CheckResult:
        if is_skipped(result):
            return to_failed(self)

        return result


@final
class Advisory(ResultMapper):
    def __map_result__(self, result: CheckResult, /) -> CheckResult:
        if is_failed(result):
            return Skipped(reason=get_reason(result))

        return result


@final
class WithError(ResultMapper):
    def __map_result__(self, result: CheckResult, /) -> CheckResult:
        if not is_failed(result):
            return result

        failed = as_failed(result)

        return Failed(
            reason=self.resolve_exc_message(failed.reason),
            status_code=self.resolve_exc_status_code(failed.status_code),
            code=self.resolve_exc_code(failed.code),
            headers=self.resolve_exc_headers(failed.headers),
        )


class ExcHandler(PermissionWrapper):
    exceptions: Exceptions

    async def check_permissions(self) -> CheckResult:
        # covers the wrapped permission's *dependency resolution* as well as its check,
        # so a dependency that raises is caught at any depth
        try:
            return await lazy_check_permission(self.permission)
        except self.exceptions as exc:
            return self.__on_exc__(exc)

    @abstractmethod
    def __on_exc__(self, exc: BaseException, /) -> CheckResult:
        pass


@final
class SkipOnExc(ExcHandler):
    def __on_exc__(self, exc: BaseException, /) -> CheckResult:
        # a skip reason never reaches the client, so it is safe to keep the exception here
        return Skipped(reason=repr(exc))


@final
class FailOnExc(ExcHandler):
    def __on_exc__(self, exc: BaseException, /) -> CheckResult:
        return to_failed(self)


__all__ = [
    "Advisory",
    "AllowSkipped",
    "DenySkipped",
    "ExcHandler",
    "FailOnExc",
    "ResultMapper",
    "SkipOnExc",
    "Undocumented",
    "When",
    "WhenPermission",
    "WithError",
]

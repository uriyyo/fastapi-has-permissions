from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal, NoReturn, TypeVar

from typing_extensions import TypeIs

from .types import AsyncFunc

if TYPE_CHECKING:
    from ._permissions import Permission


class SkipPermissionCheck(Exception):  # noqa: N818
    def __init__(self, reason: str | None = None) -> None:
        super().__init__(reason)
        self.reason = reason


class PermissionCheckFailed(Exception):  # noqa: N818
    def __init__(self, reason: str | None = None) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass
class Skipped:
    reason: str | None = None


@dataclass
class Failed:
    reason: str | None = None
    status_code: int | None = None
    code: str | None = None
    headers: dict[str, str] | None = None

    def __bool__(self) -> bool:
        return False


type CheckResult = bool | Skipped | Failed


def is_skipped(result: CheckResult) -> TypeIs[Skipped]:
    return isinstance(result, Skipped)


def is_failed(result: CheckResult) -> TypeIs[Failed | Literal[False]]:
    return isinstance(result, Failed) or result is False


def is_successful(result: CheckResult) -> TypeIs[Literal[True]]:
    return result is True


def skip(reason: str | None = None) -> NoReturn:
    raise SkipPermissionCheck(reason)


def fail(reason: str | None = None) -> NoReturn:
    raise PermissionCheckFailed(reason)


TAsyncFunc = TypeVar("TAsyncFunc", bound=AsyncFunc)


async def call_permissions_check(
    permission: Permission,
    /,
    *args: Any,
    **kwargs: Any,
) -> CheckResult:
    try:
        result = await permission.check_permissions(*args, **kwargs)
    except PermissionCheckFailed as exc:
        return _to_failed(permission, reason=exc.reason)
    except SkipPermissionCheck as exc:
        return _to_skipped(reason=exc.reason)

    match result:
        case False:
            return _to_failed(permission)
        case _:
            return result


def _to_skipped(reason: str | None = None) -> Skipped:
    return Skipped(reason=reason)


def _to_failed(permission: Permission, /, reason: str | None = None) -> Failed:
    return Failed(
        reason=reason or permission.get_exc_message(),
        status_code=permission.get_exc_status_code(),
        code=permission.get_exc_code(),
        headers=permission.get_exc_headers(),
    )


__all__ = [
    "CheckResult",
    "Failed",
    "PermissionCheckFailed",
    "SkipPermissionCheck",
    "Skipped",
    "call_permissions_check",
    "fail",
    "is_failed",
    "is_skipped",
    "is_successful",
    "skip",
]

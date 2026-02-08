from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, NoReturn, TypeAlias, TypeVar

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

    def __bool__(self) -> bool:
        return False


CheckResult: TypeAlias = bool | Skipped | Failed


def is_skipped(result: CheckResult) -> TypeIs[Skipped]:
    return isinstance(result, Skipped)


def is_failed(result: CheckResult) -> TypeIs[Failed]:
    return isinstance(result, Failed)


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
        return Failed(reason=exc.reason or permission.get_exc_message())
    except SkipPermissionCheck as exc:
        return Skipped(reason=exc.reason)

    match result:
        case False:
            return Failed(reason=permission.get_exc_message())
        case _:
            return result


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
    "skip",
]

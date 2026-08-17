from __future__ import annotations

from dataclasses import field, replace
from typing import TYPE_CHECKING, Any, Literal, NoReturn

from fastapi_injected import MakeDataclass
from typing_extensions import TypeIs

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


type Outcome = Literal["success", "failed", "skipped"]


class Source(MakeDataclass):
    name: str
    outcome: Outcome
    reason: str | None = None
    children: tuple[Source, ...] = ()
    operator: str | None = None

    def __str__(self) -> str:
        return self.render()

    def render(self, *, nested: bool = False) -> str:
        if self.operator:
            joined = f" {self.operator} ".join(child.render(nested=True) for child in self.children)

            return f"({joined})" if nested else joined

        label = f"{self.outcome}: {self.reason}" if self.reason else self.outcome

        if self.children:
            inner = ", ".join(child.render() for child in self.children)

            return f"{self.name}({inner})[{label}]"

        return f"{self.name}[{label}]"


class Skipped(MakeDataclass):
    reason: str | None = None
    source: Source | None = field(default=None, compare=False)


class Failed(MakeDataclass):
    reason: str | None = None
    status_code: int | None = None
    code: str | None = None
    headers: dict[str, str] | None = None
    source: Source | None = field(default=None, compare=False)

    def __bool__(self) -> bool:
        return False


type CheckResult = bool | Skipped | Failed


def is_skipped(result: CheckResult) -> TypeIs[Skipped]:
    return isinstance(result, Skipped)


def is_failed(result: CheckResult) -> TypeIs[Failed | Literal[False]]:
    return isinstance(result, Failed) or result is False


def is_successful(result: CheckResult) -> TypeIs[Literal[True]]:
    return result is True


def get_reason(result: CheckResult, /) -> str | None:
    match result:
        case Skipped(reason=reason) | Failed(reason=reason):
            return reason
        case _:
            return None


def as_failed(result: CheckResult, /, fallback: Failed | None = None) -> Failed:
    if isinstance(result, Failed):
        return result

    if fallback is not None:
        return fallback

    return Failed()


def skip(reason: str | None = None) -> NoReturn:
    raise SkipPermissionCheck(reason)


def fail(reason: str | None = None) -> NoReturn:
    raise PermissionCheckFailed(reason)


async def call_permissions_check(
    permission: Permission,
    /,
    *args: Any,
    **kwargs: Any,
) -> CheckResult:
    try:
        result = await permission.check_permissions(*args, **kwargs)
    except PermissionCheckFailed as exc:
        return to_failed(permission, reason=exc.reason)
    except SkipPermissionCheck as exc:
        return to_skipped(permission, reason=exc.reason)

    match result:
        case False:
            return to_failed(permission)
        case _:
            return result


def to_skipped(permission: Permission, /, reason: str | None = None) -> Skipped:
    return Skipped(
        reason=reason,
        source=Source(trace_name(permission), "skipped", reason),
    )


def to_failed(permission: Permission, /, reason: str | None = None) -> Failed:
    final_reason = reason or permission.get_exc_message()

    return Failed(
        reason=final_reason,
        status_code=permission.get_exc_status_code(),
        code=permission.get_exc_code(),
        headers=permission.get_exc_headers(),
        source=Source(trace_name(permission), "failed", final_reason),
    )


def trace_name(permission: Permission, /) -> str:
    return permission.__trace_name__ or type(permission).__name__


def outcome_of(result: CheckResult, /) -> Outcome:
    if is_successful(result):
        return "success"

    return "skipped" if is_skipped(result) else "failed"


def source_of(permission: Permission, result: CheckResult, /) -> Source:
    match result:
        case Failed(source=Source() as source) | Skipped(source=Source() as source):
            return source
        case _:
            return Source(trace_name(permission), outcome_of(result), get_reason(result))


def with_source[TResult: CheckResult](result: TResult, source: Source, /) -> TResult:
    if isinstance(result, Failed | Skipped):
        return replace(result, source=source)

    return result


__all__ = [
    "CheckResult",
    "Failed",
    "PermissionCheckFailed",
    "SkipPermissionCheck",
    "Skipped",
    "Source",
    "as_failed",
    "call_permissions_check",
    "fail",
    "get_reason",
    "is_failed",
    "is_skipped",
    "is_successful",
    "outcome_of",
    "skip",
    "source_of",
    "to_failed",
    "to_skipped",
    "trace_name",
    "with_source",
]

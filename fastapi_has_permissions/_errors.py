from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, ClassVar, NoReturn, cast

from fastapi import HTTPException, status

if TYPE_CHECKING:
    from ._permissions import Permission
    from ._results import Source


class PermissionDeniedError(Exception):
    def __init__(  # noqa: PLR0913 - one keyword per field of the denial it reports
        self,
        message: str,
        /,
        *,
        status_code: int | None = None,
        code: str | None = None,
        headers: dict[str, str] | None = None,
        permission: Permission | None = None,
        source: Source | None = None,
    ) -> None:
        super().__init__(message)

        self.message = message
        self.status_code = status_code
        self.code = code
        self.headers = headers
        self.permission = permission
        # the branch of the permission tree that produced this denial, for logs
        self.source = source

    def to_http_exception(self) -> HTTPException:
        detail: Any = self.message

        if self.code:
            detail = {"code": self.code, "message": detail}

        return HTTPException(
            status_code=self.status_code or status.HTTP_403_FORBIDDEN,
            detail=detail,
            headers=self.headers,
        )


class SyntheticScopeError(RuntimeError):
    def __init__(self) -> None:
        super().__init__(
            "a strict evaluator refuses a fabricated request - pass request= to "
            "PermissionEvaluator.scope(), or drop strict= to evaluate without one",
        )


@dataclass
class ErrorConfig:
    message: str | None = field(default=None, kw_only=True)
    status_code: int | None = field(default=None, kw_only=True)
    code: str | None = field(default=None, kw_only=True)
    headers: dict[str, str] | None = field(default=None, kw_only=True)

    default_exc_message: ClassVar[str] = "Permission denied"
    default_exc_status_code: ClassVar[int] = status.HTTP_403_FORBIDDEN
    default_exc_code: ClassVar[str | None] = None
    default_exc_headers: ClassVar[dict[str, str] | None] = None

    # the `get_exc_*` methods are the extension point - override them for a dynamic error config
    def get_exc_message(self) -> str:
        return self.message or self.default_exc_message

    def get_exc_status_code(self) -> int:
        return self.status_code or self.default_exc_status_code

    def get_exc_code(self) -> str | None:
        return self.code or self.default_exc_code

    def get_exc_headers(self) -> dict[str, str] | None:
        return self.headers or self.default_exc_headers

    # all four resolve the same way: an explicit value on this instance wins,
    # then the value propagated from the failing child, then this instance's own error config
    def resolve_exc_message(self, message: str | None = None) -> str:
        return self.message or message or self.get_exc_message()

    def resolve_exc_status_code(self, status_code: int | None = None) -> int:
        return self.status_code or status_code or self.get_exc_status_code()

    def resolve_exc_code(self, code: str | None = None) -> str | None:
        return self.code or code or self.get_exc_code()

    def resolve_exc_headers(self, headers: dict[str, str] | None = None) -> dict[str, str] | None:
        return self.headers or headers or self.get_exc_headers()

    def has_default_error_config(self) -> bool:
        return self.message is None and self.status_code is None and self.code is None and self.headers is None

    def build_error(
        self,
        message: str | None = None,
        status_code: int | None = None,
        code: str | None = None,
        headers: dict[str, str] | None = None,
        source: Source | None = None,
    ) -> PermissionDeniedError:
        return PermissionDeniedError(
            self.resolve_exc_message(message),
            status_code=self.resolve_exc_status_code(status_code),
            code=self.resolve_exc_code(code),
            headers=self.resolve_exc_headers(headers),
            permission=cast("Permission", self),
            source=source,
        )

    def raise_error(
        self,
        message: str | None = None,
        status_code: int | None = None,
        code: str | None = None,
        headers: dict[str, str] | None = None,
        source: Source | None = None,
    ) -> NoReturn:
        raise self.build_error(message, status_code, code, headers, source)


__all__ = [
    "ErrorConfig",
    "PermissionDeniedError",
    "SyntheticScopeError",
]

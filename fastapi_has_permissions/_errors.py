from dataclasses import dataclass, field
from typing import Any, ClassVar, NoReturn

from fastapi import HTTPException, status


@dataclass
class HTTPExcRaiser:
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

    def build_http_exception(
        self,
        message: str | None = None,
        status_code: int | None = None,
        code: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> HTTPException:
        detail: Any = self.resolve_exc_message(message)

        if final_code := self.resolve_exc_code(code):
            detail = {"code": final_code, "message": detail}

        return HTTPException(
            status_code=self.resolve_exc_status_code(status_code),
            detail=detail,
            headers=self.resolve_exc_headers(headers),
        )

    def raise_http_exception(
        self,
        message: str | None = None,
        status_code: int | None = None,
        code: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> NoReturn:
        raise self.build_http_exception(message, status_code, code, headers)


__all__ = [
    "HTTPExcRaiser",
]

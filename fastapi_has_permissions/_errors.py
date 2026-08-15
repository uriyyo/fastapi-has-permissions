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

    def get_exc_message(self) -> str:
        return self.message or self.default_exc_message

    def get_exc_status_code(self) -> int:
        return self.status_code or self.default_exc_status_code

    def get_exc_code(self) -> str | None:
        return self.code or self.default_exc_code

    def get_exc_headers(self) -> dict[str, str] | None:
        return self.headers or self.default_exc_headers

    def has_default_error_config(self) -> bool:
        return self.message is None and self.status_code is None and self.code is None and self.headers is None

    def raise_http_exception(
        self,
        message: str | None,
        status_code: int | None = None,
        code: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> NoReturn:
        # all four fields resolve the same way: an explicit value on this instance wins,
        # then the value propagated from the failing child, then this class default
        detail: Any = self.message or message or self.default_exc_message

        if final_code := self.code or code or self.default_exc_code:
            detail = {"code": final_code, "message": detail}

        raise HTTPException(
            status_code=self.status_code or status_code or self.default_exc_status_code,
            detail=detail,
            headers=self.headers or headers or self.default_exc_headers,
        )


__all__ = [
    "HTTPExcRaiser",
]

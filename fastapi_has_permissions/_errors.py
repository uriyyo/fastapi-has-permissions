from dataclasses import dataclass, field
from typing import ClassVar, NoReturn

from fastapi import HTTPException, status


@dataclass
class HTTPExcRaiser:
    message: str | None = field(default=None, kw_only=True)
    status_code: int | None = field(default=None, kw_only=True)

    default_exc_message: ClassVar[str] = "Permission denied"
    default_exc_status_code: ClassVar[int] = status.HTTP_403_FORBIDDEN

    def get_exc_message(self) -> str:
        return self.message or self.default_exc_message

    def get_exc_status_code(self) -> int:
        return self.status_code or self.default_exc_status_code

    def raise_http_exception(self, message: str | None) -> NoReturn:
        raise HTTPException(
            status_code=self.get_exc_status_code(),
            detail=message or self.get_exc_message(),
        )


__all__ = [
    "HTTPExcRaiser",
]

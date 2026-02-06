from dataclasses import dataclass
from typing import Any, ClassVar, NoReturn

from fastapi import HTTPException, status


class PermissionCheckError(Exception):
    def __init__(self, message: str | None) -> None:
        super().__init__(message)
        self.message = message or "Permission check failed"


@dataclass
class HTTPExcRaiser:
    default_exc_message: ClassVar[str] = "Permission denied"
    default_exc_status_code: ClassVar[int] = status.HTTP_403_FORBIDDEN

    def get_exc_message(self) -> str:
        return self.default_exc_message

    def get_exc_status_code(self) -> int:
        return self.default_exc_status_code

    def raise_http_exception(self, message: str | None) -> NoReturn:
        raise HTTPException(
            status_code=self.get_exc_status_code(),
            detail=self.get_http_exception_detail(message),
        )

    def get_http_exception_detail(self, message: str | None) -> Any:
        return {"detail": message or self.get_exc_message()}


__all__ = [
    "HTTPExcRaiser",
    "PermissionCheckError",
]

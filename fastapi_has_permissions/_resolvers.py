from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from fastapi.exceptions import RequestValidationError
from fastapi_injected import resolve

from ._bases import ForceDataclass
from ._deps_args import remap_deps_args
from ._results import CheckResult, Skipped, SkipPermissionCheck, call_permissions_check

if TYPE_CHECKING:
    from ._permissions import Permission


class PermissionResolver(ForceDataclass):
    permission: Permission

    def __post_init__(self) -> None:
        self.__signature__ = self.permission.__check_signature__()

    def __get_depends__(self) -> Any:
        return self.permission.__resolver_to_depends__(self)

    @remap_deps_args
    async def __call__(self, *args: Any, **kwargs: Any) -> CheckResult:
        return await call_permissions_check(self.permission, *args, **kwargs)


def to_validation_error(exc: ValueError, /) -> RequestValidationError | None:
    match exc.args:
        case ([dict(), *_] as errors,):
            return RequestValidationError(errors)
        case _:
            return None


async def lazy_check_permission(permission: Permission, /) -> CheckResult:
    try:
        return cast("CheckResult", await resolve(PermissionResolver(permission)))
    except SkipPermissionCheck as exc:
        return Skipped(reason=exc.reason)
    except ValueError as exc:
        if validation_error := to_validation_error(exc):
            raise validation_error from exc

        raise


__all__ = [
    "PermissionResolver",
    "lazy_check_permission",
    "to_validation_error",
]

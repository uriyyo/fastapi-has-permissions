from collections.abc import Callable, Generator
from typing import TYPE_CHECKING, ClassVar, Generic, Self, cast

from fastapi import Request
from fastapi_injected import resolve
from fastapi_injected.types import DepReturn
from typing_extensions import TypeVar

from ._bases import ForceDataclass, IdentityHashMixin
from ._permissions import Permission
from .common import Deny

TResource = TypeVar("TResource", default=None)


class _DefaultResource:
    async def __call__(self) -> None:
        return None


class Policy(ForceDataclass, IdentityHashMixin, Generic[TResource]):
    if TYPE_CHECKING:
        __resource__: ClassVar[Callable[..., DepReturn[TResource]]]
    else:
        __resource__ = _DefaultResource()

    read: ClassVar[Permission] = Deny()
    create: ClassVar[Permission] = Deny()
    update: ClassVar[Permission] = Deny()
    delete: ClassVar[Permission] = Deny()
    default: ClassVar[Permission] = Deny()

    @classmethod
    def bind(cls, resource_dep: Callable[..., DepReturn[TResource]]) -> type[Self]:
        class _BoundedPolicy(cls):  # type: ignore[ty:shadowed-type-variable,ty:unsupported-base]
            __resource__ = resource_dep

        return cast(type[Self], _BoundedPolicy)

    def __get_permissions__(self, request: Request) -> Generator[Permission]:
        match request.method.upper():
            case "GET" | "QUERY" | "HEAD":
                yield self.read
            case "POST":
                yield self.create
            case "PUT" | "PATCH":
                yield self.update
            case "DELETE":
                yield self.delete
            case _:
                yield self.default

    async def __call__(self, request: Request) -> None:
        for permission in self.__get_permissions__(request):
            await resolve(permission)


__all__ = [
    "Policy",
]

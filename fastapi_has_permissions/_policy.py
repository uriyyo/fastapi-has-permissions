from collections.abc import Collection, Generator, Iterable
from typing import TYPE_CHECKING, Any, ClassVar, Generic, Self, cast

from fastapi import Request
from fastapi.params import Depends
from fastapi_injected import MakeDataclass, resolve
from typing_extensions import TypeVar

from ._permissions import Permission
from .common import Deny
from .types import Resource

TResource = TypeVar("TResource", default=None)


class _DefaultResource:
    async def __call__(self) -> None:
        return None


class Policy(MakeDataclass, Generic[TResource]):
    if TYPE_CHECKING:
        # a `ClassVar` may not reference `TResource`, so the resource type is tied to the
        # policy through `bind` and `Requires` rather than through this declaration
        __resource__: ClassVar[Resource[Any]]
    else:
        __resource__ = _DefaultResource()

    read: ClassVar[Permission] = Deny()
    create: ClassVar[Permission] = Deny()
    update: ClassVar[Permission] = Deny()
    delete: ClassVar[Permission] = Deny()
    default: ClassVar[Permission] = Deny()

    @classmethod
    def bind(cls, resource_dep: Resource[TResource]) -> type[Self]:
        class _BoundedPolicy(cls):  # type: ignore[ty:shadowed-type-variable,ty:unsupported-base]
            __resource__ = resource_dep

        return cast(type[Self], _BoundedPolicy)

    def __get_permissions_for_method__(self, method: str, /) -> Generator[Permission]:
        match method.upper():
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

    def __get_permissions__(self, request: Request) -> Generator[Permission]:
        yield from self.__get_permissions_for_method__(request.method)

    def __lazy_depends__(self, methods: Collection[str], /) -> Iterable[Depends]:
        for method in methods:
            for permission in self.__get_permissions_for_method__(method):
                yield from permission.__lazy_depends__(methods)

    async def __call__(self, request: Request) -> None:
        for permission in self.__get_permissions__(request):
            await resolve(permission)


__all__ = [
    "Policy",
]

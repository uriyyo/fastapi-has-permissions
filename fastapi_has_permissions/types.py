from collections.abc import Callable, Collection, Coroutine, Iterable, Sequence
from typing import TYPE_CHECKING, Any, Protocol, TypeAlias, runtime_checkable

from fastapi.params import Depends
from fastapi_injected import DepFactory
from fastapi_injected.types import DepReturn
from typing_extensions import TypeVar

if TYPE_CHECKING:
    from typing_extensions import TypeForm

    type Dep[R] = TypeForm[R]
else:
    from fastapi_injected import Dep

type Resource[R] = Callable[..., DepReturn[R]] | Dep[R]

_TAny = TypeVar("_TAny", default=Any)

type Deps = Sequence[Dep[Any]]

Func: TypeAlias = Callable[..., _TAny]
AsyncFunc: TypeAlias = Callable[..., Coroutine[Any, Any, _TAny]]

type Exceptions = tuple[type[BaseException], ...]


@runtime_checkable
class HasLazyDepends(Protocol):
    def __lazy_depends__(self, methods: Collection[str], /) -> Iterable[Depends]:
        pass


__all__ = [
    "AsyncFunc",
    "Dep",
    "DepFactory",
    "Deps",
    "Exceptions",
    "Func",
    "HasLazyDepends",
    "Resource",
]

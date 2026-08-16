from collections.abc import Callable, Collection, Coroutine, Iterable, Sequence
from typing import TYPE_CHECKING, Any, Protocol, TypeAlias, runtime_checkable

from fastapi.params import Depends
from fastapi_injected import DepFactory
from fastapi_injected.types import DepReturn
from typing_extensions import TypeVar

if TYPE_CHECKING:
    from typing import Annotated

    from typing_extensions import TypeForm

    # `Dep[R]` is a marker held as a *value*: a permission field stores the marker itself
    type Dep[R] = TypeForm[R]
    # `Resolved[R]` is the same marker in *annotation* position: what a check receives is the `R`
    type Resolved[R] = Annotated[R, Depends()]
else:
    from fastapi_injected import Dep

    Resolved = Dep

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
    "Resolved",
    "Resource",
]

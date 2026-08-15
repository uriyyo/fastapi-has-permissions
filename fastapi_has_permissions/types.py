from collections.abc import Callable, Coroutine, Sequence
from typing import TYPE_CHECKING, Any, TypeAlias

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

Args: TypeAlias = tuple[_TAny, ...]
Kwargs: TypeAlias = dict[str, _TAny]

type Deps = Sequence[Dep[Any]]

Func: TypeAlias = Callable[..., _TAny]
AsyncFunc: TypeAlias = Callable[..., Coroutine[Any, Any, _TAny]]

type Exceptions = tuple[type[BaseException], ...]

__all__ = [
    "Args",
    "AsyncFunc",
    "Dep",
    "DepFactory",
    "Deps",
    "Exceptions",
    "Func",
    "Kwargs",
    "Resource",
]

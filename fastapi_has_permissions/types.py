from collections.abc import Callable, Coroutine, Sequence
from typing import Any, TypeAlias

from fastapi_injected import Dep, DepFactory
from typing_extensions import TypeVar

_TAny = TypeVar("_TAny", default=Any)

Args: TypeAlias = tuple[_TAny, ...]
Kwargs: TypeAlias = dict[str, _TAny]

Deps: TypeAlias = Sequence[Dep[Any]]

Func: TypeAlias = Callable[..., _TAny]
AsyncFunc: TypeAlias = Callable[..., Coroutine[Any, Any, _TAny]]

Exceptions: TypeAlias = tuple[type[BaseException], ...]

__all__ = [
    "Args",
    "AsyncFunc",
    "Dep",
    "DepFactory",
    "Deps",
    "Exceptions",
    "Func",
    "Kwargs",
]

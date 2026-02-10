from collections.abc import Callable, Coroutine, Sequence
from typing import Any, Literal, TypeAlias

from typing_extensions import TypeVar

from ._dep import Dep

_TAny = TypeVar("_TAny", default=Any)

Args: TypeAlias = tuple[_TAny, ...]
Kwargs: TypeAlias = dict[str, _TAny]

Deps: TypeAlias = Sequence[Dep[Any]]

DepScope: TypeAlias = Literal["function", "request"]

Func: TypeAlias = Callable[..., _TAny]
AsyncFunc: TypeAlias = Callable[..., Coroutine[Any, Any, _TAny]]

Exceptions: TypeAlias = tuple[type[BaseException], ...]

__all__ = [
    "Args",
    "AsyncFunc",
    "Dep",
    "DepScope",
    "Deps",
    "Exceptions",
    "Func",
    "Kwargs",
]

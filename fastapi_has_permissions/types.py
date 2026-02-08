from collections.abc import Callable, Coroutine, Sequence
from typing import Any, Literal, TypeAlias

from typing_extensions import TypeVar

_TAny = TypeVar("_TAny", default=Any)

Args: TypeAlias = tuple[_TAny, ...]
Kwargs: TypeAlias = dict[str, _TAny]

# TODO: Add typing for dependency input param
Dep: TypeAlias = Any
Deps: TypeAlias = Sequence[Any]

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

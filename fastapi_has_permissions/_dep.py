from dataclasses import dataclass
from typing import TYPE_CHECKING, Annotated, Any, TypeAlias, cast

from typing_extensions import Self, TypeVar

if TYPE_CHECKING:
    _T = TypeVar("_T", default=Any)
    Dep: TypeAlias = Annotated[_T, ...]

else:

    @dataclass
    class Dep:
        tp: Any

        def __class_getitem__(cls, item: Any) -> Self:
            if isinstance(item, tuple):
                raise TypeError("Dep can only be subscripted with a single type")

            return cls(item)  # type: ignore[too-many-positional-arguments]


def is_dep(obj: Any, /) -> bool:
    _tp = cast("type[Any]", Dep)

    if isinstance(obj, type) and issubclass(obj, _tp):
        return True

    return isinstance(obj, _tp)


def unwrap_dep(obj: Any, /) -> Any:
    if is_dep(obj):
        if isinstance(obj, type):
            return Any

        return obj.tp

    msg = f"Expected a Dep, got {type(obj).__name__}"
    raise TypeError(msg)


__all__ = [
    "Dep",
    "is_dep",
    "unwrap_dep",
]

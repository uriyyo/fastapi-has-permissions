from typing import Annotated, Any, TypeVar, get_args, get_origin

from fastapi import params


def _dep_metadata(obj: Any, /) -> tuple[Any, ...]:
    if get_origin(obj) is not Annotated:
        return ()

    return get_args(obj)[1:]


def is_dep(obj: Any, /) -> bool:
    return any(isinstance(meta, params.Depends) and meta.dependency is None for meta in _dep_metadata(obj))


def unwrap_dep(obj: Any, /) -> Any:
    if not is_dep(obj):
        msg = f"Expected a Dep, got {type(obj).__name__}"
        raise TypeError(msg)

    match get_args(obj)[0]:
        case TypeVar():  # bare `Dep`, used without a type argument
            return Any
        case tp:
            return tp


__all__ = [
    "is_dep",
    "unwrap_dep",
]

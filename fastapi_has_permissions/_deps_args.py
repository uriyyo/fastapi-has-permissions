import inspect
from functools import wraps
from itertools import count, takewhile
from typing import Any, TypeVar, cast

from .types import AsyncFunc, Deps, Func


def get_dep_arg_name(index: int = 0, /) -> str:
    return f"__positional_arg_{index}__"


def get_signature_with_deps(func: Func, deps: Deps) -> inspect.Signature:
    sign = inspect.signature(func)

    # skip the self + first N parameters that correspond to parametrized dependencies
    other_deps = [*sign.parameters.values()][len(deps) :]

    return sign.replace(
        parameters=[
            *[
                inspect.Parameter(
                    name=get_dep_arg_name(i),
                    kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    annotation=dep,
                )
                for i, dep in enumerate(deps)
            ],
            *other_deps,
        ],
    )


TAsyncFunc = TypeVar("TAsyncFunc", bound=AsyncFunc)


def remap_deps_args(func: TAsyncFunc) -> TAsyncFunc:
    @wraps(func)
    async def wrapper(self: Any, **kwargs: Any) -> Any:
        possible_args = (get_dep_arg_name(i) for i in count())
        args = [kwargs.pop(arg) for arg in takewhile(lambda key: key in kwargs, possible_args)]
        return await func(self, *args, **kwargs)

    return cast("TAsyncFunc", wrapper)


__all__ = [
    "get_dep_arg_name",
    "get_signature_with_deps",
    "remap_deps_args",
]

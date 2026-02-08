import inspect
from collections.abc import Iterable
from functools import wraps
from itertools import count, takewhile
from typing import Annotated, Any, TypeVar, cast

from fastapi.dependencies.utils import get_typed_signature
from fastapi.params import Depends

from .types import AsyncFunc, Dep, Deps, Func


def get_dep_arg_name(index: int = 0, /) -> str:
    return f"__positional_arg_{index}__"


def _get_dep_annotation(dep: Any, /) -> Any:
    if isinstance(dep, Depends):
        return Annotated[Any, dep]

    return dep


def get_signature_with_deps(func: Func, deps: Deps) -> inspect.Signature:
    sign = get_typed_signature(func)

    # skip the self + first N parameters that correspond to parametrized dependencies
    other_deps = [*sign.parameters.values()][len(deps) :]

    return sign.replace(
        parameters=[
            *[
                inspect.Parameter(
                    name=get_dep_arg_name(i),
                    kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    annotation=_get_dep_annotation(dep),
                )
                for i, dep in enumerate(deps)
            ],
            *other_deps,
        ],
    )


def deps_from_func_signature(func: Func) -> Iterable[str]:
    sign = get_typed_signature(func)

    for param in sign.parameters.values():
        if param.annotation is Dep:
            yield param.name


def signature_with_params(params: Iterable[inspect.Parameter]) -> inspect.Signature:
    return inspect.Signature(parameters=[*params])


TAsyncFunc = TypeVar("TAsyncFunc", bound=AsyncFunc)


def remap_deps_args(func: TAsyncFunc) -> TAsyncFunc:
    @wraps(func)
    async def wrapper(self: Any, **kwargs: Any) -> Any:
        possible_args = (get_dep_arg_name(i) for i in count())
        args = [kwargs.pop(arg) for arg in takewhile(lambda key: key in kwargs, possible_args)]
        return await func(self, *args, **kwargs)

    return cast("TAsyncFunc", wrapper)


__all__ = [
    "deps_from_func_signature",
    "get_dep_arg_name",
    "get_signature_with_deps",
    "remap_deps_args",
    "signature_with_params",
]

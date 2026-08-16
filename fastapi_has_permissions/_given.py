from typing import Annotated, Any, cast

from fastapi.params import Depends

from ._bases import ForceDataclass
from .types import Dep


class _Constant[R](ForceDataclass):
    value: R

    async def __call__(self) -> R:
        return self.value


def Given[R](value: R, /) -> Dep[R]:  # noqa: N802
    return cast("Dep[R]", Annotated[Any, Depends(_Constant(value))])


__all__ = [
    "Given",
]

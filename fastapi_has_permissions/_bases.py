from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, dataclass_transform


def _hash_with_fallback(original_hash_func: Callable[[Any], int]) -> Callable[[Any], int]:
    def _hash_with_fallback_wrapper(self: Any) -> int:
        try:
            return original_hash_func(self)
        except TypeError:
            return id(self)

    return _hash_with_fallback_wrapper


_dataclass_params = {"init", "repr", "eq", "order", "unsafe_hash", "frozen", "match_args", "kw_only"}


@dataclass_transform(field_specifiers=(field,))
class ForceDataclass:
    def __init_subclass__(
        cls,
        *,
        no_hash_override: bool = False,
        **kwargs: Any,
    ) -> None:
        # consumed here rather than forwarded, otherwise they reach
        # object.__init_subclass__ and raise TypeError
        kwargs.setdefault("unsafe_hash", True)
        dt_kwargs = {param: kwargs.pop(param) for param in _dataclass_params & kwargs.keys()}

        super().__init_subclass__(**kwargs)

        dataclass(cls, **dt_kwargs)

        if no_hash_override:
            return

        cls.__hash__ = _hash_with_fallback(cls.__hash__)  # type: ignore[ty:invalid-assignment]

    if TYPE_CHECKING:

        def __hash__(self: Any) -> int:
            pass


__all__ = [
    "ForceDataclass",
]

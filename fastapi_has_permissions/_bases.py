import inspect
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, dataclass_transform


def _identity_hash(self: Any) -> int:
    return id(self)


# This is a workaround to add a default __hash__ method to dataclasses that don't define one.
# We need this because dataclasses are not checking for __hash__ method in base classes.
#
# In general, we need to add __hash__ method cause it required by fastapi's dependency injection system
# for object to be hashable to be used as a dependency.
class IdentityHashMixin:
    def __init_subclass__(
        cls,
        *,
        no_hash_override: bool = False,
        **kwargs: Any,
    ) -> None:
        # consumed here rather than forwarded, otherwise it reaches
        # object.__init_subclass__ and raises TypeError
        super().__init_subclass__(**kwargs)

        if no_hash_override:
            return

        cls.__hash__ = _identity_hash


@dataclass
class SignatureOverride(ABC):
    def __post_init__(self) -> None:
        self.__signature__ = self.__get_signature__()

    @abstractmethod
    def __get_signature__(self) -> inspect.Signature:
        pass


_dataclass_params = {"init", "repr", "eq", "order", "unsafe_hash", "frozen", "match_args", "kw_only"}


@dataclass_transform(field_specifiers=(field,))
class ForceDataclass:
    def __init_subclass__(cls, **kwargs: Any) -> None:
        # consumed here rather than forwarded, otherwise they reach
        # object.__init_subclass__ and raise TypeError
        dt_kwargs = {param: kwargs.pop(param) for param in _dataclass_params & kwargs.keys()}

        super().__init_subclass__(**kwargs)

        dataclass(cls, **dt_kwargs)


__all__ = [
    "ForceDataclass",
    "IdentityHashMixin",
    "SignatureOverride",
]

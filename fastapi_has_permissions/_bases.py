import inspect
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from typing_extensions import dataclass_transform


def _identity_hash(self: Any) -> int:
    return id(self)


# This is a workaround to add a default __hash__ method to dataclasses that don't define one.
# We need this because dataclasses are not checking for __hash__ method in base classes.
#
# In general, we need to add __hash__ method cause it required by fastapi's dependency injection system
# for object to be hashable to be used as a dependency.
class IdentityHashMixin:
    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)

        if kwargs.get("no_hash_override", False):
            return

        cls.__hash__ = _identity_hash  # type: ignore[assignment]


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
        super().__init_subclass__(**kwargs)

        dt_kwargs = {param: kwargs[param] for param in _dataclass_params & kwargs.keys()}
        dataclass(cls, **dt_kwargs)


__all__ = [
    "ForceDataclass",
    "IdentityHashMixin",
    "SignatureOverride",
]

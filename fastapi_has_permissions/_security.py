from typing import Any

from fastapi import params
from fastapi_injected import MakeDataclass


class Security(MakeDataclass, params.Security, frozen=True):
    def __post_init__(self) -> None:
        super().__post_init__()
        object.__setattr__(self, "scopes", tuple(self.scopes or ()))


def as_hashable_security(depends: Any, /) -> Any:
    if isinstance(depends, params.Security) and not isinstance(depends, Security):
        return Security(
            depends.dependency,
            depends.use_cache,
            depends.scope,
            depends.scopes,
        )

    return depends


__all__ = [
    "Security",
    "as_hashable_security",
]

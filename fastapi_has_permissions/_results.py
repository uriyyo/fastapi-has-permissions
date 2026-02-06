from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

from typing_extensions import TypeIs


class SkipPermissionCheck(Exception):  # noqa: N818
    def __init__(self, reason: str | None = None) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass
class Skipped:
    reason: str | None = None


CheckResult: TypeAlias = bool | Skipped


def is_skipped(result: CheckResult) -> TypeIs[Skipped]:
    return isinstance(result, Skipped)


__all__ = [
    "CheckResult",
    "SkipPermissionCheck",
    "Skipped",
    "is_skipped",
]

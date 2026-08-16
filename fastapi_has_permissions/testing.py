from ._evaluate import evaluate
from ._permissions import Permission
from ._results import (
    CheckResult,
    Failed,
    Skipped,
    as_failed,
    is_skipped,
    is_successful,
    to_failed,
)

_SKIP_HINT = "a skip denies at the root, but it is not a denial - use `assert_skipped` to assert an abstention"


def _name(permission: Permission, /) -> str:
    return type(permission).__name__


def _describe(result: CheckResult, /) -> str:
    match result:
        case Failed(reason=reason, status_code=status_code, code=code):
            described = f"denied with {status_code} {reason!r}"

            return f"{described} (code={code!r})" if code else described
        case Skipped(reason=reason):
            return f"abstained ({reason!r})" if reason else "abstained"
        case True:
            return "allowed"
        case _:
            return "denied"


def _mismatch(name: str, outcome: str, field: str, actual: object, expected: object) -> str:
    return f"{name} {outcome}, but its {field} was {actual!r} rather than the expected {expected!r}"


async def assert_allowed(permission: Permission, /) -> CheckResult:
    """Assert that `permission` succeeds, and return its result."""
    result = await evaluate(permission)

    if not is_successful(result):
        hint = f". Note that {_SKIP_HINT}" if is_skipped(result) else ""
        msg = f"{_name(permission)} was expected to allow, but it {_describe(result)}{hint}"

        raise AssertionError(msg)

    return result


async def assert_denied(
    permission: Permission,
    /,
    *,
    reason: str | None = None,
    status_code: int | None = None,
    code: str | None = None,
) -> Failed:
    """Assert that `permission` denies, optionally with a given error configuration.

    An abstention is *not* a denial here, even though one denies at the root - assert it with
    `assert_skipped` so a rule that stopped applying cannot pass as a rule that refused.
    """
    result = await evaluate(permission)
    name = _name(permission)

    if is_skipped(result):
        msg = f"{name} was expected to deny, but it {_describe(result)} - {_SKIP_HINT}"

        raise AssertionError(msg)

    if is_successful(result):
        msg = f"{name} was expected to deny, but it allowed"

        raise AssertionError(msg)

    failed = as_failed(result, to_failed(permission))

    for field, actual, expected in (
        ("reason", failed.reason, reason),
        ("status_code", failed.status_code, status_code),
        ("code", failed.code, code),
    ):
        if expected is not None and actual != expected:
            raise AssertionError(_mismatch(name, "denied", field, actual, expected))

    return failed


async def assert_skipped(permission: Permission, /, *, reason: str | None = None) -> Skipped:
    """Assert that `permission` abstains - that it has no opinion about this caller."""
    result = await evaluate(permission)
    name = _name(permission)

    if not is_skipped(result):
        msg = f"{name} was expected to abstain, but it {_describe(result)}"

        raise AssertionError(msg)

    if reason is not None and result.reason != reason:
        raise AssertionError(_mismatch(name, "abstained", "reason", result.reason, reason))

    return result


__all__ = [
    "assert_allowed",
    "assert_denied",
    "assert_skipped",
]

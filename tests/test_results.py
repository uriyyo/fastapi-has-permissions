import pytest

from fastapi_has_permissions import (
    Failed,
    Skipped,
    as_failed,
    get_reason,
    is_failed,
    is_skipped,
    is_successful,
)


@pytest.mark.parametrize(
    ("result", "expected"),
    [
        pytest.param(Failed(reason="denied"), "denied", id="failed"),
        pytest.param(Skipped(reason="abstained"), "abstained", id="skipped"),
        pytest.param(Failed(), None, id="failed-without-a-reason"),
        pytest.param(Skipped(), None, id="skipped-without-a-reason"),
        # a bare boolean carries nothing to explain itself with
        pytest.param(True, None, id="true"),
        pytest.param(False, None, id="false"),
    ],
)
def test_get_reason(result, expected) -> None:
    assert get_reason(result) == expected


def test_as_failed_keeps_the_failure_a_result_already_carries() -> None:
    failed = Failed(reason="denied", status_code=404, code="gone", headers={"X": "1"})

    assert as_failed(failed) is failed
    # an existing failure is never replaced, even when a fallback is offered
    assert as_failed(failed, Failed(reason="fallback")) is failed


@pytest.mark.parametrize(
    "result",
    [
        pytest.param(Skipped(reason="abstained"), id="skipped"),
        pytest.param(False, id="false"),
        pytest.param(True, id="true"),
    ],
)
def test_as_failed_falls_back_for_anything_carrying_no_failure(result) -> None:
    assert as_failed(result) == Failed()

    fallback = Failed(reason="fallback", status_code=404)

    assert as_failed(result, fallback) is fallback


def test_the_result_predicates_stay_mutually_consistent() -> None:
    # `is_failed` covers a bare `False` as well as a `Failed`, and the three never overlap
    for result, successful, failed, skipped in [
        (True, True, False, False),
        (False, False, True, False),
        (Failed(), False, True, False),
        (Skipped(), False, False, True),
    ]:
        assert is_successful(result) is successful, result
        assert is_failed(result) is failed, result
        assert is_skipped(result) is skipped, result

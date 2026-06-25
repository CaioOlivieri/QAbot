from qabot.agent import reconcile
from qabot.agent.reconcile import ProductionBug


def _bug(
    number: int = 1,
    severity: str = "critical",
    file_refs: tuple[str, ...] = ("ops.py",),
    created_at: str = "2026-06-20T00:00:00Z",
) -> ProductionBug:
    return ProductionBug(number, severity, file_refs, created_at)


def test_extract_file_refs_from_traceback() -> None:
    text = 'Traceback:\n  File "/app/src/ops.py", line 12, in run\n    boom()'
    assert reconcile.extract_file_refs(text) == ("ops.py",)


def test_extract_file_refs_from_inline_path() -> None:
    assert reconcile.extract_file_refs("crash in payments/charge.py near the top") == (
        "charge.py",
    )


def test_extract_file_refs_none_when_no_code() -> None:
    assert reconcile.extract_file_refs("the checkout button does nothing") == ()


def test_within_window_filters_old_bugs() -> None:
    recent = _bug(number=1, created_at="2026-06-01T00:00:00Z")
    old = _bug(number=2, created_at="2026-01-01T00:00:00Z")
    kept = reconcile.within_window([recent, old], 90, "2026-06-25T00:00:00Z")
    assert [b.number for b in kept] == [1]


def test_count_critical() -> None:
    bugs = [
        _bug(severity="critical"),
        _bug(severity="warning"),
        _bug(severity="critical"),
    ]
    assert reconcile.count_critical(bugs) == 2


def test_escape_rate_math() -> None:
    result = reconcile.escape_rate(caught=9, escaped=1)
    assert result.escape_rate == 10.0
    assert result.dre == 90.0


def test_escape_rate_no_defects_is_none() -> None:
    result = reconcile.escape_rate(caught=0, escaped=0)
    assert result.escape_rate is None
    assert result.dre is None


def test_detection_breakdown_three_buckets() -> None:
    flagged = _bug(number=1, file_refs=("ops.py",))
    undetected = _bug(number=2, file_refs=("other.py",))
    unmatched = _bug(number=3, file_refs=())
    result = reconcile.detection_breakdown(
        [flagged, undetected, unmatched], flagged_files={"ops.py"}
    )
    assert [b.number for b in result["flagged"]] == [1]
    assert [b.number for b in result["undetected"]] == [2]
    assert [b.number for b in result["unmatched"]] == [3]

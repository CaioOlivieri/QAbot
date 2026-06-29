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


def test_detection_breakdown_uses_fix_commit_files_when_no_text_ref() -> None:
    # No stack-trace ref, but the fixing commit touched a flagged file → flagged.
    rescued = ProductionBug(1, "critical", (), "2026-06-20T00:00:00Z", ("ops.py",))
    # Fix touched a file QA never flagged → undetected (still out of unmatched).
    elsewhere = ProductionBug(2, "critical", (), "2026-06-20T00:00:00Z", ("new.py",))
    # No signal at all → unmatched.
    blank = ProductionBug(3, "critical", (), "2026-06-20T00:00:00Z", ())
    result = reconcile.detection_breakdown(
        [rescued, elsewhere, blank], flagged_files={"ops.py"}
    )
    assert [b.number for b in result["flagged"]] == [1]
    assert [b.number for b in result["undetected"]] == [2]
    assert [b.number for b in result["unmatched"]] == [3]


def test_qa_observation_start_is_earliest_run_with_a_commit() -> None:
    runs = [
        {"timestamp": "2026-06-10T00:00:00Z", "commit_sha": None},
        {"timestamp": "2026-06-12T00:00:00Z", "commit_sha": "abc"},
        {"timestamp": "2026-06-15T00:00:00Z", "commit_sha": "def"},
    ]
    assert reconcile.qa_observation_start(runs) == "2026-06-12T00:00:00Z"


def test_qa_observation_start_none_when_no_commit_recorded() -> None:
    runs = [{"timestamp": "2026-06-10T00:00:00Z", "commit_sha": None}]
    assert reconcile.qa_observation_start(runs) is None


def test_catchable_excludes_bugs_reported_before_qa_observed() -> None:
    before = _bug(number=1, created_at="2026-06-01T00:00:00Z")
    after = _bug(number=2, created_at="2026-06-20T00:00:00Z")
    kept = reconcile.catchable([before, after], anchor_iso="2026-06-12T00:00:00Z")
    assert [b.number for b in kept] == [2]


def test_catchable_keeps_all_when_anchor_is_none() -> None:
    bugs = [_bug(number=1, created_at="2020-01-01T00:00:00Z")]
    assert reconcile.catchable(bugs, anchor_iso=None) == bugs


def test_catchable_with_provenance_includes_reachable() -> None:
    bugs = [_bug(number=1)]
    out = reconcile.catchable_with_provenance(bugs, {1: True}, anchor_iso=None)
    assert [b.number for b in out] == [1]


def test_catchable_with_provenance_excludes_unreachable() -> None:
    bugs = [_bug(number=1)]
    assert reconcile.catchable_with_provenance(bugs, {1: False}, anchor_iso=None) == []


def test_catchable_with_provenance_falls_back_to_time_anchor_when_absent() -> None:
    early = _bug(number=1, created_at="2020-01-01T00:00:00Z")
    late = _bug(number=2, created_at="2020-12-01T00:00:00Z")
    # neither bug is in the provenance map → the #46 time-anchor decides
    out = reconcile.catchable_with_provenance(
        [early, late], {}, anchor_iso="2020-06-01T00:00:00Z"
    )
    assert [b.number for b in out] == [2]


def test_catchable_with_provenance_absent_and_no_anchor_keeps_all() -> None:
    bugs = [_bug(number=1), _bug(number=2)]
    out = reconcile.catchable_with_provenance(bugs, {}, anchor_iso=None)
    assert [b.number for b in out] == [1, 2]


def test_catchable_with_provenance_mixes_szz_and_fallback() -> None:
    szz = _bug(number=1, created_at="2020-01-01T00:00:00Z")  # SZZ says reachable
    proxy = _bug(number=2, created_at="2020-01-01T00:00:00Z")  # absent + pre-anchor
    out = reconcile.catchable_with_provenance(
        [szz, proxy], {1: True}, anchor_iso="2020-06-01T00:00:00Z"
    )
    assert [b.number for b in out] == [1]

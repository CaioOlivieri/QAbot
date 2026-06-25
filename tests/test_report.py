import re

from qabot.agent.reconcile import EscapeRate
from qabot.agent.report import compute_scores, generate_report


def _bug(status: str, severity: str = "critical") -> dict[str, object]:
    return {
        "file": "m.py",
        "line": 7,
        "description": "off-by-one",
        "severity": severity,
        "status": status,
        "evidence": "",
    }


def _score(report: str) -> float:
    match = re.search(r"Quality Score: ([\d.]+)", report)
    assert match is not None
    return float(match.group(1))


def test_suspected_bug_does_not_affect_score() -> None:
    clean = generate_report("/p", {}, {}, [], [], [], [])
    with_suspect = generate_report("/p", {}, {}, [], [], [], [_bug("suspected")])
    assert _score(with_suspect) == _score(clean)


def test_confirmed_semantic_bug_lowers_score() -> None:
    clean = generate_report("/p", {}, {}, [], [], [], [])
    with_confirmed = generate_report("/p", {}, {}, [], [], [], [_bug("confirmed")])
    assert _score(with_confirmed) < _score(clean)


def test_discarded_bug_is_not_shown_or_scored() -> None:
    clean = generate_report("/p", {}, {}, [], [], [], [])
    with_discarded = generate_report("/p", {}, {}, [], [], [], [_bug("discarded")])
    assert _score(with_discarded) == _score(clean)


def test_suspected_appears_in_for_review_section() -> None:
    report = generate_report("/p", {}, {}, [], [], [], [_bug("suspected")])
    assert "For Review" in report
    assert "off-by-one" in report


def test_confirmed_appears_in_semantic_section() -> None:
    report = generate_report("/p", {}, {}, [], [], [], [_bug("confirmed")])
    assert "Semantic Bugs (LLM, confirmed by execution)" in report
    assert "off-by-one" in report


def test_coverage_section_renders_module_row_with_delta() -> None:
    report = generate_report("/p", {"m.py": 50.0}, {"m.py": 80.0}, [], [], [], [])
    assert "| m.py | 50.0% | 80.0% | +30.0% |" in report


def test_ast_bug_row_is_rendered() -> None:
    ast_bug = {
        "file": "m.py",
        "line": 3,
        "severity": "critical",
        "category": "bare_except",
        "description": "Bare except clause",
    }
    report = generate_report("/p", {}, {}, [ast_bug], [], [], [])
    assert "| m.py | 3 | critical | bare_except | Bare except clause |" in report


def test_dynamic_bug_row_is_rendered() -> None:
    dyn_bug = {
        "file": "m.py",
        "line": 9,
        "test_name": "test_boom",
        "severity": "warning",
        "error_type": "ValueError",
        "description": "invalid input",
    }
    report = generate_report("/p", {}, {}, [], [dyn_bug], [], [])
    assert "test_boom" in report
    assert "ValueError" in report


def test_api_result_rows_render_pass_and_fail() -> None:
    results = [
        {
            "url": "https://x.com",
            "method": "GET",
            "expected_status": 200,
            "status_code": 200,
            "passed": True,
        },
        {
            "url": "https://y.com",
            "method": "GET",
            "expected_status": 200,
            "status_code": 0,
            "passed": False,
            "error": "timeout",
        },
    ]
    report = generate_report("/p", {}, {}, [], [], results, [])
    assert "✓ passed" in report
    assert "✗ failed (error)" in report


def _run_meta() -> dict[str, object]:
    return {
        "run_id": "r2",
        "timestamp": "2026-06-25T00:00:00Z",
        "commit_sha": "abcdef1234567",
        "thresholds": {"min_coverage": 80.0, "max_new_criticals": 0},
    }


def _diff(new=None, coverage_after=95.0) -> dict[str, object]:
    return {
        "new": new or [],
        "regressed": [],
        "resolved": [],
        "coverage": {
            "before": 80.0,
            "after": coverage_after,
            "delta": coverage_after - 80.0,
        },
    }


def test_scorecard_gate_pass_with_upward_trend() -> None:
    report = generate_report(
        "/p",
        {},
        {"m.py": 90.0},
        [],
        [],
        [],
        [],
        diff=_diff(),
        run_meta=_run_meta(),
        previous_quality=50.0,
    )
    assert "Gate: PASS" in report
    assert "▲" in report
    assert "## Changes Since Last Run" in report
    assert "Run r2" in report
    assert "commit abcdef1" in report


def test_scorecard_gate_fails_on_new_critical() -> None:
    crit = {"file": "m.py", "line": 1, "severity": "critical", "category": "x"}
    report = generate_report(
        "/p",
        {},
        {"m.py": 95.0},
        [],
        [],
        [],
        [],
        diff=_diff(new=[crit]),
        run_meta=_run_meta(),
        previous_quality=90.0,
    )
    assert "Gate: FAIL" in report
    assert "1 new critical defect(s)" in report
    assert "| new | m.py | 1 | critical | x |" in report


def test_scorecard_gate_fails_on_low_coverage_first_run() -> None:
    report = generate_report(
        "/p",
        {},
        {"m.py": 50.0},
        [],
        [],
        [],
        [],
        diff=_diff(coverage_after=50.0),
        run_meta=_run_meta(),
        previous_quality=None,
    )
    assert "Gate: FAIL" in report
    assert "(first run)" in report


def test_compute_scores_has_four_keys() -> None:
    scores = compute_scores({"m.py": 100.0}, [], [], [], [])
    assert set(scores) == {"quality", "coverage", "bug", "api"}


def test_scorecard_trend_down_and_flat() -> None:
    down = generate_report(
        "/p",
        {},
        {"m.py": 50.0},
        [],
        [],
        [],
        [],
        diff=_diff(coverage_after=50.0),
        run_meta=_run_meta(),
        previous_quality=100.0,
    )
    assert "▼" in down
    flat = generate_report(
        "/p",
        {},
        {"m.py": 90.0},
        [],
        [],
        [],
        [],
        diff=_diff(),
        run_meta=_run_meta(),
        previous_quality=96.0,
    )
    assert "▬" in flat


def test_report_renders_dre_kpi() -> None:
    reconciliation = {
        "escape": EscapeRate(caught=9, escaped=1, escape_rate=10.0, dre=90.0),
        "breakdown": {"flagged": [1], "undetected": [], "unmatched": [2]},
        "window_days": 90,
    }
    report = generate_report(
        "/p",
        {},
        {"m.py": 90.0},
        [],
        [],
        [],
        [],
        diff=_diff(),
        run_meta=_run_meta(),
        reconciliation=reconciliation,
    )
    assert "Critical Defect Escape Rate (DRE)" in report
    assert "Critical escape rate: 10.0%" in report
    assert "DRE 90.0%" in report
    assert "✗ below the 95% professional minimum" in report
    assert "Capers Jones" in report
    assert "1 flagged-but-shipped" in report


def test_report_dre_no_defects_in_window() -> None:
    reconciliation = {
        "escape": EscapeRate(0, 0, None, None),
        "breakdown": {"flagged": [], "undetected": [], "unmatched": []},
        "window_days": 30,
    }
    report = generate_report(
        "/p",
        {},
        {},
        [],
        [],
        [],
        [],
        diff=_diff(),
        run_meta=_run_meta(),
        reconciliation=reconciliation,
    )
    assert "No critical defects recorded" in report
    assert "last 30 days" in report

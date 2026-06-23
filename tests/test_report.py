import re

from qabot.agent.report import generate_report


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

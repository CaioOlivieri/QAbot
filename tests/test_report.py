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

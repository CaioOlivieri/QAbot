from pathlib import Path

from qabot import state


def _ast_bug(
    file: str = "ops.py", line: int = 10, category: str = "mutable_default"
) -> dict[str, object]:
    return {
        "file": file,
        "line": line,
        "category": category,
        "severity": "warning",
        "description": "mutable default argument",
    }


def _confirmed(file: str = "ops.py", line: int = 3) -> dict[str, object]:
    return {
        "file": file,
        "line": line,
        "severity": "critical",
        "description": "is_even inverted",
        "status": "confirmed",
    }


def test_load_state_missing_returns_empty(tmp_path: Path) -> None:
    loaded = state.load_state(str(tmp_path))
    assert loaded["runs"] == []
    assert loaded["version"] == state.STATE_VERSION


def test_load_state_corrupt_returns_empty(tmp_path: Path) -> None:
    reports = tmp_path / "reports"
    reports.mkdir()
    (reports / state.STATE_FILENAME).write_text("{ not json")
    assert state.load_state(str(tmp_path))["runs"] == []


def test_save_then_load_round_trip(tmp_path: Path) -> None:
    original = state.load_state(str(tmp_path))
    original["runs"].append({"run_id": "r1", "findings": []})
    state.save_state(str(tmp_path), original)
    assert state.load_state(str(tmp_path))["runs"][0]["run_id"] == "r1"


def test_extract_findings_only_keeps_confirmed_suspicions() -> None:
    suspected = [_confirmed(), {**_confirmed(line=9), "status": "suspected"}]
    found = state.extract_findings([_ast_bug()], [], suspected)
    sources = sorted(f["source"] for f in found)
    assert sources == ["semantic", "static"]


def test_fingerprint_is_stable_identity() -> None:
    a = state.extract_findings([_ast_bug()], [], [])[0]
    b = state.extract_findings([_ast_bug(line=10)], [], [])[0]
    assert state.fingerprint(a) == state.fingerprint(b)


def test_diff_findings_new_resolved_regressed() -> None:
    bug_a = state.extract_findings([_ast_bug(line=1)], [], [])
    bug_b = state.extract_findings([_ast_bug(line=2)], [], [])
    bug_c = state.extract_findings([_ast_bug(line=3)], [], [])

    historical = {state.fingerprint(bug_a[0]), state.fingerprint(bug_b[0])}
    previous = bug_a  # last run had only A
    current = bug_b + bug_c  # B returns after a gap, C is brand new

    diff = state.diff_findings(previous, current, historical)
    assert [f["line"] for f in diff["new"]] == [3]
    assert [f["line"] for f in diff["regressed"]] == [2]
    assert [f["line"] for f in diff["resolved"]] == [1]


def test_diff_coverage_delta() -> None:
    delta = state.diff_coverage({"a.py": 50.0}, {"a.py": 80.0})
    assert delta["before"] == 50.0
    assert delta["after"] == 80.0
    assert delta["delta"] == 30.0


def test_record_run_twice_persists_ledger_and_diff(tmp_path: Path) -> None:
    project = str(tmp_path)

    # First run: one static bug, fresh coverage.
    _, first = state.record_run(
        project, [_ast_bug()], [], [], {"ops.py": 60.0}, commit_sha="aaa"
    )
    assert [f["line"] for f in first["new"]] == [10]
    assert first["resolved"] == []
    assert first["coverage"]["delta"] == 60.0

    # Second run: the bug is gone, coverage improved.
    full_state, second = state.record_run(
        project, [], [], [], {"ops.py": 90.0}, commit_sha="bbb"
    )
    runs = full_state["runs"]
    assert len(runs) == 2
    assert runs[0]["findings"][0]["status"] == "new"
    assert [f["line"] for f in second["resolved"]] == [10]
    assert second["new"] == []
    assert second["coverage"]["delta"] == 30.0


def test_record_run_marks_regression(tmp_path: Path) -> None:
    project = str(tmp_path)
    state.record_run(project, [_ast_bug()], [], [], {"ops.py": 60.0})
    state.record_run(project, [], [], [], {"ops.py": 60.0})  # resolved
    full_state, third = state.record_run(
        project, [_ast_bug()], [], [], {"ops.py": 60.0}
    )  # back again
    assert [f["line"] for f in third["regressed"]] == [10]
    assert third["new"] == []
    assert full_state["runs"][-1]["findings"][0]["status"] == "regressed"


def test_extract_findings_uses_error_type_for_dynamic() -> None:
    dynamic = [
        {
            "file": "ops.py",
            "line": 4,
            "severity": "critical",
            "error_type": "ZeroDivisionError",
            "description": "division by zero",
        }
    ]
    found = state.extract_findings([], dynamic, [])
    assert found[0]["source"] == "dynamic"
    assert found[0]["category"] == "ZeroDivisionError"


def test_record_run_marks_unchanged_finding_existing(tmp_path: Path) -> None:
    project = str(tmp_path)
    state.record_run(project, [_ast_bug()], [], [], {"ops.py": 60.0})
    full_state, second = state.record_run(
        project, [_ast_bug()], [], [], {"ops.py": 60.0}
    )
    assert second["new"] == []
    assert second["regressed"] == []
    assert full_state["runs"][-1]["findings"][0]["status"] == "existing"


def test_load_state_wrong_shape_returns_empty(tmp_path: Path) -> None:
    reports = tmp_path / "reports"
    reports.mkdir()
    (reports / state.STATE_FILENAME).write_text('{"runs": "not a list"}')
    assert state.load_state(str(tmp_path))["runs"] == []


def test_current_commit_none_outside_repo(tmp_path: Path) -> None:
    assert state.current_commit(str(tmp_path)) is None


def test_summarize_diff_one_line() -> None:
    diff = {
        "new": [1, 2],
        "regressed": [],
        "resolved": [3],
        "coverage": {"before": 60.0, "after": 80.0, "delta": 20.0},
    }
    summary = state.summarize_diff(diff)
    assert "2 new" in summary
    assert "1 resolved" in summary
    assert "+20.0%" in summary

import os
from unittest.mock import patch

import qabot.agent.smoke as smoke

_PYTEST_OUTPUT = (
    "Name                  Stmts   Miss  Cover\n"
    "-----------------------------------------\n"
    "qabot/ops.py             20      1    95%\n"
    "-----------------------------------------\n"
    "TOTAL                    20      1    95%\n"
    "1 passed\n"
)


def _critical(file: str = "qabot/ops.py") -> dict[str, object]:
    return {
        "file": file,
        "line": 3,
        "severity": "critical",
        "category": "bare_except",
        "description": "Bare except clause without exception type",
    }


def test_run_smoke_passes_with_good_coverage_and_no_criticals(tmp_path) -> None:
    with (
        patch.object(smoke, "_measure_coverage", return_value={"qabot/ops.py": 95.0}),
        patch.object(smoke, "_source_ast_bugs", return_value=[]),
    ):
        result = smoke.run_smoke(str(tmp_path))
    assert result.verdict == "PASS"
    assert result.passed is True
    assert result.reasons == []
    # Report and machine-readable exports are persisted for CI to upload.
    assert os.path.exists(tmp_path / "reports" / "qa_report.md")
    assert os.path.exists(tmp_path / "reports" / "qa-results.xml")


def test_run_smoke_fails_on_low_coverage(tmp_path) -> None:
    with (
        patch.object(smoke, "_measure_coverage", return_value={"qabot/ops.py": 50.0}),
        patch.object(smoke, "_source_ast_bugs", return_value=[]),
    ):
        result = smoke.run_smoke(str(tmp_path))
    assert result.verdict == "FAIL"
    assert any("coverage" in r for r in result.reasons)


def test_run_smoke_fails_on_new_critical_defect(tmp_path) -> None:
    with (
        patch.object(smoke, "_measure_coverage", return_value={"qabot/ops.py": 95.0}),
        patch.object(smoke, "_source_ast_bugs", return_value=[_critical()]),
    ):
        result = smoke.run_smoke(str(tmp_path))
    assert result.verdict == "FAIL"
    assert any("critical" in r for r in result.reasons)


def test_run_smoke_never_touches_the_ledger(tmp_path) -> None:
    """A pull request must not write the trend of the default branch."""
    with (
        patch.object(smoke, "_measure_coverage", return_value={"qabot/ops.py": 95.0}),
        patch.object(smoke, "_source_ast_bugs", return_value=[]),
    ):
        smoke.run_smoke(str(tmp_path))
    assert not os.path.exists(tmp_path / "reports" / "qabot_state.json")


def test_run_smoke_runs_without_an_llm_api_key(tmp_path, monkeypatch) -> None:
    """The smoke tier is LLM-free, so it must work on fork PRs with no secret."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with (
        patch.object(smoke, "_measure_coverage", return_value={"qabot/ops.py": 95.0}),
        patch.object(smoke, "_source_ast_bugs", return_value=[]),
    ):
        result = smoke.run_smoke(str(tmp_path))
    assert result.verdict == "PASS"


def test_measure_coverage_parses_pytest_term_output(tmp_path) -> None:
    with patch.object(smoke, "run_command", return_value=(0, _PYTEST_OUTPUT, "")):
        coverage = smoke._measure_coverage(str(tmp_path))
    assert coverage == {"qabot/ops.py": 95.0}


def test_source_ast_bugs_skips_vendored_directories(tmp_path) -> None:
    files = [
        os.path.join("project", ".venv", "lib", "dep.py"),
        os.path.join("project", "qabot", "ops.py"),
    ]
    with (
        patch.object(smoke, "list_files", return_value=files),
        patch.object(smoke, "analyze_file_ast", side_effect=lambda f: [{"file": f}]),
    ):
        bugs = smoke._source_ast_bugs("project")
    assert bugs == [{"file": os.path.join("project", "qabot", "ops.py")}]


def test_smoke_cmd_honors_env_override(monkeypatch) -> None:
    monkeypatch.setenv("QABOT_SMOKE_CMD", "pytest -x tests/unit")
    assert smoke._smoke_pytest_cmd() == ["pytest", "-x", "tests/unit"]

import os
import xml.etree.ElementTree as ET
from unittest.mock import patch

import pytest

import qabot.agent.smoke as smoke
from qabot.agent.exports import coverage_xml_has_lines


@pytest.fixture(autouse=True)
def _silence_notify():
    """run_smoke notifies at the end; never fire real notifications in tests."""
    with patch.object(smoke.notify, "send"):
        yield


_PYTEST_OUTPUT = (
    "Name                  Stmts   Miss  Cover\n"
    "-----------------------------------------\n"
    "qabot/ops.py             20      1    95%\n"
    "-----------------------------------------\n"
    "TOTAL                    20      1    95%\n"
    "1 passed\n"
)

_REAL_COVERAGE_XML = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<coverage line-rate="0.9500" branch-rate="0" version="coverage.py">\n'
    "  <packages>\n"
    '    <package name="." line-rate="0.9500">\n'
    "      <classes>\n"
    '        <class name="ops.py" filename="ops.py" line-rate="0.9500">\n'
    "          <methods/>\n"
    "          <lines>\n"
    '            <line number="1" hits="1"/>\n'
    "          </lines>\n"
    "        </class>\n"
    "      </classes>\n"
    "    </package>\n"
    "  </packages>\n"
    "</coverage>"
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
        patch.object(
            smoke, "_collect_coverage", return_value=({"qabot/ops.py": 95.0}, None)
        ),
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
        patch.object(
            smoke, "_collect_coverage", return_value=({"qabot/ops.py": 50.0}, None)
        ),
        patch.object(smoke, "_source_ast_bugs", return_value=[]),
    ):
        result = smoke.run_smoke(str(tmp_path))
    assert result.verdict == "FAIL"
    assert any("coverage" in r for r in result.reasons)


def test_run_smoke_fails_on_new_critical_defect(tmp_path) -> None:
    with (
        patch.object(
            smoke, "_collect_coverage", return_value=({"qabot/ops.py": 95.0}, None)
        ),
        patch.object(smoke, "_source_ast_bugs", return_value=[_critical()]),
    ):
        result = smoke.run_smoke(str(tmp_path))
    assert result.verdict == "FAIL"
    assert any("critical" in r for r in result.reasons)


def test_run_smoke_never_touches_the_ledger(tmp_path) -> None:
    """A pull request must not write the trend of the default branch."""
    with (
        patch.object(
            smoke, "_collect_coverage", return_value=({"qabot/ops.py": 95.0}, None)
        ),
        patch.object(smoke, "_source_ast_bugs", return_value=[]),
    ):
        smoke.run_smoke(str(tmp_path))
    assert not os.path.exists(tmp_path / "reports" / "qabot_state.json")


def test_run_smoke_runs_without_an_llm_api_key(tmp_path, monkeypatch) -> None:
    """The smoke tier is LLM-free, so it must work on fork PRs with no secret."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with (
        patch.object(
            smoke, "_collect_coverage", return_value=({"qabot/ops.py": 95.0}, None)
        ),
        patch.object(smoke, "_source_ast_bugs", return_value=[]),
    ):
        result = smoke.run_smoke(str(tmp_path))
    assert result.verdict == "PASS"


def test_collect_coverage_returns_real_xml_when_present(tmp_path) -> None:
    def _fake_run(cmd, cwd):
        xml_arg = next(a for a in cmd if a.startswith("--cov-report=xml:"))
        xml_path = xml_arg.split(":", 1)[1]
        os.makedirs(os.path.dirname(xml_path), exist_ok=True)
        with open(xml_path, "w") as f:
            f.write(_REAL_COVERAGE_XML)
        return 0, _PYTEST_OUTPUT, ""

    with patch.object(smoke, "run_command", side_effect=_fake_run):
        coverage, real_xml = smoke._collect_coverage(str(tmp_path))
    assert coverage == {"qabot/ops.py": 95.0}
    assert real_xml is not None
    assert coverage_xml_has_lines(real_xml)


def test_collect_coverage_returns_none_xml_when_no_lines(tmp_path) -> None:
    summary_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<coverage line-rate="0.9500" branch-rate="0" version="qabot">\n'
        "  <packages/>\n"
        "</coverage>"
    )

    def _fake_run(cmd, cwd):
        xml_arg = next(a for a in cmd if a.startswith("--cov-report=xml:"))
        xml_path = xml_arg.split(":", 1)[1]
        os.makedirs(os.path.dirname(xml_path), exist_ok=True)
        with open(xml_path, "w") as f:
            f.write(summary_xml)
        return 0, _PYTEST_OUTPUT, ""

    with patch.object(smoke, "run_command", side_effect=_fake_run):
        coverage, real_xml = smoke._collect_coverage(str(tmp_path))
    assert coverage == {"qabot/ops.py": 95.0}
    assert real_xml is None


def test_collect_coverage_handles_unreadable_xml(tmp_path) -> None:
    # If the temp XML vanishes before it is read, read_text raises OSError;
    # the run must fall back to None coverage instead of propagating.
    def _fake_run(cmd, cwd):
        xml_arg = next(a for a in cmd if a.startswith("--cov-report=xml:"))
        os.remove(xml_arg.split(":", 1)[1])
        return 0, _PYTEST_OUTPUT, ""

    with patch.object(smoke, "run_command", side_effect=_fake_run):
        coverage, real_xml = smoke._collect_coverage(str(tmp_path))
    assert coverage == {"qabot/ops.py": 95.0}
    assert real_xml is None


def test_collect_coverage_cleans_up_tempfile(tmp_path) -> None:
    # mkstemp writes to the system temp dir, so capture the actual path the run
    # was told to use and assert _collect_coverage's finally-block removed it.
    captured: dict[str, str] = {}

    def _fake_run(cmd, cwd):
        xml_arg = next(a for a in cmd if a.startswith("--cov-report=xml:"))
        captured["xml_path"] = xml_arg.split(":", 1)[1]
        return 0, _PYTEST_OUTPUT, ""

    with patch.object(smoke, "run_command", side_effect=_fake_run):
        smoke._collect_coverage(str(tmp_path))
    assert captured["xml_path"]
    assert not os.path.exists(captured["xml_path"])


def test_run_smoke_writes_real_coverage_xml_to_reports(tmp_path) -> None:
    with (
        patch.object(
            smoke,
            "_collect_coverage",
            return_value=({"qabot/ops.py": 95.0}, _REAL_COVERAGE_XML),
        ),
        patch.object(smoke, "_source_ast_bugs", return_value=[]),
    ):
        smoke.run_smoke(str(tmp_path))
    cov_path = tmp_path / "reports" / "coverage.xml"
    assert cov_path.exists()
    content = cov_path.read_text()
    assert content == _REAL_COVERAGE_XML
    assert next(ET.fromstring(content).iter("line")) is not None


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

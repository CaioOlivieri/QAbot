from contextlib import contextmanager
from unittest.mock import MagicMock, mock_open, patch

import pytest

import qabot.agent.core as core
from qabot.agent.core import _parse_agent_json, _write_report


def test_parses_plain_json() -> None:
    parsed = _parse_agent_json('{"action": "list_files", "action_input": "."}')
    assert parsed["action"] == "list_files"
    assert parsed["action_input"] == "."


def test_strips_json_code_fence() -> None:
    raw = '```json\n{"action": "read_file", "action_input": "a.py"}\n```'
    assert _parse_agent_json(raw)["action"] == "read_file"


def test_strips_bare_code_fence() -> None:
    raw = '```\n{"final_answer": "done"}\n```'
    assert _parse_agent_json(raw)["final_answer"] == "done"


def test_extracts_object_from_surrounding_prose() -> None:
    raw = 'Here is my response:\n{"action": "list_files", "action_input": "."}\nDone.'
    assert _parse_agent_json(raw)["action"] == "list_files"


def test_tolerates_trailing_comma() -> None:
    raw = '{"action": "list_files", "action_input": ".",}'
    assert _parse_agent_json(raw)["action_input"] == "."


def test_tolerates_literal_newlines_in_string_value() -> None:
    raw = (
        '{"action": "write_file", "action_input": '
        '{"path": "t.py", "content": "def f():\n    return 1\n"}}'
    )
    parsed = _parse_agent_json(raw)
    assert parsed["action_input"]["content"] == "def f():\n    return 1\n"


def test_ignores_braces_inside_string_values() -> None:
    raw = '{"thought": "use a dict like {a: 1}", "action": "list_files"}'
    assert _parse_agent_json(raw)["action"] == "list_files"


def test_skips_non_json_braces_in_prose() -> None:
    raw = 'note {not json} then\n{"final_answer": "ok"}'
    assert _parse_agent_json(raw)["final_answer"] == "ok"


def test_picks_first_object_when_multiple_present() -> None:
    raw = '{"action": "list_files"} {"action": "read_file"}'
    assert _parse_agent_json(raw)["action"] == "list_files"


def test_raises_on_no_json_object() -> None:
    with pytest.raises(ValueError):
        _parse_agent_json("there is no json here at all")


def test_raises_on_json_array() -> None:
    with pytest.raises(ValueError):
        _parse_agent_json('["not", "an", "object"]')


def test_write_report_writes_under_project_path() -> None:
    m = mock_open()
    with patch("qabot.agent.core.os.makedirs") as mock_dirs:
        with patch("builtins.open", m):
            path = _write_report("/proj", "# report")
    assert path == "/proj/reports/qa_report.md"
    mock_dirs.assert_called_once_with("/proj/reports", exist_ok=True)
    m.assert_called_once_with("/proj/reports/qa_report.md", "w")
    m.return_value.write.assert_called_once_with("# report")


_ACTION = '{"thought": "look around", "action": "list_files", "action_input": "."}'
_FINAL = '{"thought": "done", "final_answer": "analysis complete"}'
_INVALID = "this is not json"
_PARSE_COVERAGE = (
    '{"thought": "coverage", "action": "parse_coverage", "action_input": "raw"}'
)
_EMPTY_DIFF = {
    "new": [],
    "regressed": [],
    "resolved": [],
    "coverage": {"before": 0.0, "after": 0.0, "delta": 0.0},
}
_STUB_STATE = {
    "runs": [
        {
            "run_id": "r1",
            "timestamp": "2026-01-01T00:00:00Z",
            "commit_sha": None,
            "scores": None,
            "findings": [],
        }
    ]
}


@contextmanager
def _patched_agent(monkeypatch, responses, dispatch_result="tool output"):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    with (
        patch.object(core, "load_dotenv"),
        patch.object(core, "genai"),
        patch.object(core, "_call_llm", side_effect=responses) as call_llm,
        patch.object(core, "_dispatch", return_value=dispatch_result) as dispatch,
        patch.object(core, "generate_report", return_value="# report") as generate,
        patch.object(core, "_write_report", return_value="report.md") as write,
        patch.object(core, "current_commit", return_value=None),
        patch.object(core, "record_run", return_value=(_STUB_STATE, _EMPTY_DIFF)),
        patch.object(core, "write_exports", return_value=[]),
        patch.object(core, "fetch_production_bugs", return_value=None),
    ):
        yield call_llm, dispatch, generate, write


def test_dispatch_routes_string_input_to_list_files() -> None:
    with patch.object(core, "list_files", return_value=["a.py"]) as list_files:
        result = core._dispatch("list_files", "/proj", "/proj")
    list_files.assert_called_once_with("/proj")
    assert "a.py" in result


def test_dispatch_parses_dict_input_for_write_file() -> None:
    with patch.object(core, "write_file") as write_file:
        result = core._dispatch(
            "write_file", {"path": "tests/test_a.py", "content": "x = 1"}, "/proj"
        )
    write_file.assert_called_once_with("/proj/tests/test_a.py", "x = 1")
    assert result == "File written successfully."


def test_dispatch_write_file_refuses_non_test_file() -> None:
    with patch.object(core, "write_file") as write_file:
        result = core._dispatch(
            "write_file", {"path": "qabot/core.py", "content": "x = 1"}, "/proj"
        )
    write_file.assert_not_called()
    assert result.startswith("Refused")


def test_dispatch_write_file_refuses_path_escaping_project() -> None:
    with patch.object(core, "write_file") as write_file:
        result = core._dispatch(
            "write_file", {"path": "../evil/test_x.py", "content": "x = 1"}, "/proj"
        )
    write_file.assert_not_called()
    assert result.startswith("Refused")


def test_dispatch_read_file_reads_inside_project() -> None:
    with patch.object(core, "read_file", return_value="content") as read_file:
        result = core._dispatch("read_file", "sub/a.py", "/proj")
    read_file.assert_called_once_with("/proj/sub/a.py")
    assert result == "content"


def test_dispatch_read_file_refuses_traversal() -> None:
    with patch.object(core, "read_file") as read_file:
        result = core._dispatch("read_file", "../evil.py", "/proj")
    read_file.assert_not_called()
    assert result.startswith("Refused")


def test_dispatch_read_file_refuses_absolute_outside() -> None:
    with patch.object(core, "read_file") as read_file:
        result = core._dispatch("read_file", "/etc/passwd", "/proj")
    read_file.assert_not_called()
    assert result.startswith("Refused")


def test_dispatch_unknown_tool_returns_message() -> None:
    assert core._dispatch("mystery", "", "/proj") == "Unknown tool: mystery"


def test_dispatch_acks_semantic_bug_tools() -> None:
    assert core._dispatch("report_suspected_bug", {}, "/p") == "Suspected bug recorded."
    assert (
        core._dispatch("resolve_suspected_bug", {}, "/p")
        == "Resolution recorded; outcome decided by the latest test run."
    )


def test_resolve_suspicion_skips_non_suspected_and_reports_no_match() -> None:
    findings = core.Findings()
    findings.suspected_bugs.append(
        {"file": "m.py", "line": 7, "status": "confirmed", "evidence": ""}
    )
    result = core._resolve_suspicion(findings, {"file": "m.py", "line": 7}, "")
    assert result == "no matching suspicion"


def test_tool_error_does_not_crash_run(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    with (
        patch.object(core, "load_dotenv"),
        patch.object(core, "genai"),
        patch.object(core, "_call_llm", side_effect=[_ACTION, _FINAL]),
        patch.object(core, "_dispatch", side_effect=RuntimeError("boom")) as dispatch,
        patch.object(core, "generate_report", return_value="# report"),
        patch.object(core, "_write_report", return_value="report.md"),
        patch.object(core, "current_commit", return_value=None),
        patch.object(core, "record_run", return_value=(_STUB_STATE, _EMPTY_DIFF)),
        patch.object(core, "write_exports", return_value=[]),
        patch.object(core, "fetch_production_bugs", return_value=None),
    ):
        result = core.run_agent("/proj")
    dispatch.assert_called_once()
    assert result == "analysis complete"


def test_accumulate_coverage_fills_before_then_after() -> None:
    findings = core.Findings()
    core._accumulate_findings("parse_coverage", "", "{'m.py': 50.0}", findings, "")
    core._accumulate_findings("parse_coverage", "", "{'m.py': 80.0}", findings, "")
    assert findings.coverage_before == {"m.py": 50.0}
    assert findings.coverage_after == {"m.py": 80.0}


def test_accumulate_extends_ast_and_dynamic_and_api() -> None:
    findings = core.Findings()
    core._accumulate_findings(
        "analyze_project_ast", "", "[{'severity': 'critical'}]", findings, ""
    )
    core._accumulate_findings(
        "parse_pytest_failures", "", "[{'severity': 'warning'}]", findings, ""
    )
    core._accumulate_findings("test_api_endpoint", "", "{'passed': True}", findings, "")
    assert findings.ast_bugs == [{"severity": "critical"}]
    assert findings.dynamic_bugs == [{"severity": "warning"}]
    assert findings.api_results == [{"passed": True}]


def test_accumulate_run_command_returns_new_last_output() -> None:
    findings = core.Findings()
    out = core._accumulate_findings("run_command", "", "pytest output", findings, "old")
    assert out == "pytest output"


def _raise_then_return(errors: list[Exception], value: str):
    seq: list = [*errors, value]

    def fake(client, messages):
        item = seq.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    return fake


def test_call_llm_with_retry_recovers_from_503(monkeypatch) -> None:
    monkeypatch.setattr(core.time, "sleep", lambda _s: None)
    monkeypatch.setattr(
        core, "_call_llm", _raise_then_return([Exception("503 UNAVAILABLE")], "ok")
    )
    assert core._call_llm_with_retry(None, []) == "ok"


def test_call_llm_with_retry_recovers_from_429(monkeypatch) -> None:
    monkeypatch.setattr(core.time, "sleep", lambda _s: None)
    monkeypatch.setattr(
        core,
        "_call_llm",
        _raise_then_return([Exception("429 RESOURCE_EXHAUSTED")], "ok"),
    )
    assert core._call_llm_with_retry(None, []) == "ok"


def test_call_llm_with_retry_gives_up_after_max_503(monkeypatch) -> None:
    monkeypatch.setattr(core.time, "sleep", lambda _s: None)

    def always_503(client, messages):
        raise RuntimeError("503 UNAVAILABLE high demand")

    monkeypatch.setattr(core, "_call_llm", always_503)
    with pytest.raises(RuntimeError, match="503"):
        core._call_llm_with_retry(None, [])


def test_call_llm_with_retry_reraises_other_errors(monkeypatch) -> None:
    monkeypatch.setattr(core.time, "sleep", lambda _s: None)

    def boom(client, messages):
        raise ValueError("400 invalid argument")

    monkeypatch.setattr(core, "_call_llm", boom)
    with pytest.raises(ValueError):
        core._call_llm_with_retry(None, [])


def test_call_llm_uses_model_from_env(monkeypatch) -> None:
    monkeypatch.setenv("QABOT_MODEL", "gemini-2.5-flash")
    client = MagicMock()
    client.models.generate_content.return_value = MagicMock(text="{}")
    core._call_llm(client, [{"role": "user", "content": "hi"}])
    kwargs = client.models.generate_content.call_args.kwargs
    assert kwargs["model"] == "gemini-2.5-flash"


def test_call_llm_defaults_model_when_env_absent(monkeypatch) -> None:
    monkeypatch.delenv("QABOT_MODEL", raising=False)
    client = MagicMock()
    client.models.generate_content.return_value = MagicMock(text="{}")
    core._call_llm(client, [{"role": "user", "content": "hi"}])
    kwargs = client.models.generate_content.call_args.kwargs
    assert kwargs["model"] == "gemini-2.5-flash-lite"


def test_ledger_critical_summary_dedupes_and_collects_files() -> None:
    runs = [
        {
            "findings": [
                {"file": "pkg/ops.py", "severity": "critical", "fingerprint": "fp1"},
                {"file": "util.py", "severity": "warning", "fingerprint": "fp2"},
            ]
        },
        {
            "findings": [
                {"file": "ops.py", "severity": "critical", "fingerprint": "fp1"}
            ]
        },
    ]
    count, files = core._ledger_critical_summary(runs)
    assert count == 1  # fp1 counted once across runs
    assert files == {"ops.py", "util.py"}


def test_run_agent_computes_reconciliation_when_configured(monkeypatch) -> None:
    from qabot.agent.reconcile import ProductionBug

    bug = ProductionBug(1, "critical", ("m.py",), "2026-01-01T00:00:00Z")
    with _patched_agent(monkeypatch, [_FINAL]) as (_c, _d, generate, _w):
        with patch.object(core, "fetch_production_bugs", return_value=[bug]):
            core.run_agent("/proj")
    reconciliation = generate.call_args.kwargs["reconciliation"]
    assert reconciliation is not None
    assert reconciliation["escape"].escaped == 1


def test_final_answer_terminates_loop(monkeypatch) -> None:
    with _patched_agent(monkeypatch, [_FINAL]) as (call_llm, _disp, generate, _write):
        result = core.run_agent("/proj")
    assert result == "analysis complete"
    assert call_llm.call_count == 1
    generate.assert_called_once()


def test_invalid_json_retries_then_continues(monkeypatch) -> None:
    with _patched_agent(monkeypatch, [_INVALID, _FINAL]) as (call_llm, *_):
        result = core.run_agent("/proj")
    assert result == "analysis complete"
    assert call_llm.call_count == 2


def test_three_invalid_json_responses_abort(monkeypatch) -> None:
    responses = [_INVALID, _INVALID, _INVALID]
    with _patched_agent(monkeypatch, responses) as (call_llm, *_):
        result = core.run_agent("/proj")
    assert result == "Aborted: 3 consecutive invalid JSON responses."
    assert call_llm.call_count == 3


def test_findings_accumulate_across_iterations(monkeypatch) -> None:
    coverage = "{'qabot/core.py': 50.0}"
    responses = [_PARSE_COVERAGE, _FINAL]
    with _patched_agent(monkeypatch, responses, dispatch_result=coverage) as (
        _call_llm,
        _disp,
        generate,
        _write,
    ):
        core.run_agent("/proj")
    coverage_before = generate.call_args.args[1]
    assert coverage_before == {"qabot/core.py": 50.0}


def test_max_iterations_reached_still_writes_report(monkeypatch) -> None:
    def always_act(client, messages):
        return _ACTION

    with _patched_agent(monkeypatch, always_act) as (call_llm, _disp, generate, write):
        result = core.run_agent("/proj")
    assert result == "Max iterations reached without a final answer."
    assert call_llm.call_count == 25
    generate.assert_called_once()
    write.assert_called_once_with("/proj", "# report")


_SUSPECT = (
    '{"thought": "off", "action": "report_suspected_bug", '
    '"action_input": {"file": "m.py", "line": 7, '
    '"description": "off-by-one", "severity": "critical"}}'
)
_RUN_COMMAND = (
    '{"thought": "run", "action": "run_command", '
    '"action_input": {"cmd": ["pytest"], "cwd": "."}}'
)
_RESOLVE = (
    '{"thought": "resolve", "action": "resolve_suspected_bug", '
    '"action_input": {"file": "m.py", "line": 7}}'
)
_FAILING_PYTEST = (
    "============================== FAILURES ==============================\n"
    "______________________ test_bug ______________________\n"
    "E   AssertionError: assert 1 == 2\n"
    "m.py:7: AssertionError\n"
    "========================= short test summary info ===\n"
)
_PASSING_PYTEST = "Return code: 0\nStdout:\n2 passed\nStderr:\n"


def test_report_suspected_bug_records_suspicion(monkeypatch) -> None:
    with _patched_agent(monkeypatch, [_SUSPECT, _FINAL]) as (_c, _d, generate, _w):
        core.run_agent("/proj")
    suspected = generate.call_args.args[6]
    assert len(suspected) == 1
    assert suspected[0]["status"] == "suspected"
    assert suspected[0]["file"] == "m.py"


def test_suspicion_confirmed_when_test_run_failed(monkeypatch) -> None:
    responses = [_SUSPECT, _RUN_COMMAND, _RESOLVE, _FINAL]
    with _patched_agent(monkeypatch, responses, dispatch_result=_FAILING_PYTEST) as (
        _c,
        _d,
        generate,
        _w,
    ):
        core.run_agent("/proj")
    assert generate.call_args.args[6][0]["status"] == "confirmed"


def test_suspicion_discarded_when_test_run_passed(monkeypatch) -> None:
    responses = [_SUSPECT, _RUN_COMMAND, _RESOLVE, _FINAL]
    with _patched_agent(monkeypatch, responses, dispatch_result=_PASSING_PYTEST) as (
        _c,
        _d,
        generate,
        _w,
    ):
        core.run_agent("/proj")
    assert generate.call_args.args[6][0]["status"] == "discarded"

from unittest.mock import mock_open, patch

import pytest

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

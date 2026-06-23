from unittest.mock import MagicMock, mock_open, patch

from qabot.tools.analyzer import analyze_file_ast, analyze_project_ast
from qabot.tools.api import detect_api_endpoints
from qabot.tools.api import test_api_endpoint as call_endpoint
from qabot.tools.fs import list_files, read_file, write_file
from qabot.tools.runner import parse_coverage, parse_pytest_failures, run_command

# ─── fs ──────────────────────────────────────────────────────────────────────


def test_list_files_returns_glob_results() -> None:
    with patch("qabot.tools.fs.glob.glob", return_value=["a.py", "b.py"]):
        assert list_files("/proj") == ["a.py", "b.py"]


def test_read_file_returns_content() -> None:
    with patch("builtins.open", mock_open(read_data="hello")):
        assert read_file("/f.py") == "hello"


def test_write_file_creates_dirs_and_writes() -> None:
    m = mock_open()
    with patch("qabot.tools.fs.os.makedirs") as mock_dirs:
        with patch("builtins.open", m):
            write_file("/some/path/f.py", "data")
    mock_dirs.assert_called_once_with("/some/path", exist_ok=True)
    m.assert_called_once_with("/some/path/f.py", "w")
    m.return_value.write.assert_called_once_with("data")


# ─── runner ──────────────────────────────────────────────────────────────────


def test_run_command_returns_tuple() -> None:
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "out"
    mock_result.stderr = ""
    with patch("qabot.tools.runner.subprocess.run", return_value=mock_result):
        rc, out, err = run_command(["ls"], "/")
    assert rc == 0
    assert out == "out"
    assert err == ""


_COVERAGE_OUTPUT = (
    "Name                   Stmts   Miss  Cover\n"
    "------------------------------------------\n"
    "qabot/tools/fs.py          5      1    80%\n"
    "qabot/tools/runner.py      8      2    75%\n"
    "TOTAL                     13      3    77%\n"
)


def test_parse_coverage_extracts_modules() -> None:
    result = parse_coverage(_COVERAGE_OUTPUT)
    assert result == {"qabot/tools/fs.py": 80.0, "qabot/tools/runner.py": 75.0}


def test_parse_coverage_excludes_total() -> None:
    assert "TOTAL" not in parse_coverage(_COVERAGE_OUTPUT)


def test_parse_coverage_empty_input() -> None:
    assert parse_coverage("") == {}


_PYTEST_CRITICAL_PROD = (
    "============================== FAILURES ==============================\n"
    "______________________ test_something ______________________\n"
    "\n"
    "    def test_something():\n"
    ">       risky()\n"
    "E   RuntimeError: boom\n"
    "\n"
    "qabot/tools/fs.py:10: RuntimeError\n"
    "========================= short test summary info =========================\n"
)

_PYTEST_CRITICAL_ASSERT = (
    "============================== FAILURES ==============================\n"
    "______________________ test_values ______________________\n"
    "\n"
    "    def test_values():\n"
    ">       assert result == expected\n"
    "E   AssertionError: assert 1 == 2\n"
    "\n"
    "tests/test_foo.py:5: AssertionError\n"
    "========================= short test summary info =========================\n"
)

_PYTEST_WARNING = (
    "============================== FAILURES ==============================\n"
    "______________________ test_warning ______________________\n"
    "\n"
    "    def test_warning():\n"
    '>       parse("bad")\n'
    "E   ValueError: invalid input\n"
    "\n"
    "tests/test_foo.py:8: ValueError\n"
    "========================= short test summary info =========================\n"
)

_PYTEST_MULTI = (
    "============================== FAILURES ==============================\n"
    "______________________ test_first ______________________\n"
    "\n"
    "E   AssertionError: assert 1 == 2\n"
    "\n"
    "tests/test_a.py:3: AssertionError\n"
    "______________________ test_second ______________________\n"
    "\n"
    "E   TypeError: unsupported type\n"
    "\n"
    "tests/test_b.py:7: TypeError\n"
    "========================= short test summary info =========================\n"
)


def test_parse_pytest_failures_critical_prod_file() -> None:
    result = parse_pytest_failures(_PYTEST_CRITICAL_PROD)
    assert len(result) == 1
    f = result[0]
    assert f["severity"] == "critical"
    assert f["file"] == "qabot/tools/fs.py"
    assert f["line"] == 10
    assert f["test_name"] == "test_something"
    assert f["error_type"] == "RuntimeError"


def test_parse_pytest_failures_critical_assertion() -> None:
    result = parse_pytest_failures(_PYTEST_CRITICAL_ASSERT)
    assert len(result) == 1
    f = result[0]
    assert f["severity"] == "critical"
    assert f["error_type"] == "AssertionError"
    assert f["test_name"] == "test_values"


def test_parse_pytest_failures_warning() -> None:
    result = parse_pytest_failures(_PYTEST_WARNING)
    assert len(result) == 1
    assert result[0]["severity"] == "warning"
    assert result[0]["error_type"] == "ValueError"


def test_parse_pytest_failures_empty() -> None:
    assert parse_pytest_failures("") == []


def test_parse_pytest_failures_multiple_blocks() -> None:
    result = parse_pytest_failures(_PYTEST_MULTI)
    assert len(result) == 2
    assert result[0]["test_name"] == "test_first"
    assert result[1]["test_name"] == "test_second"


# ─── api ─────────────────────────────────────────────────────────────────────


def test_detect_api_endpoints_finds_url() -> None:
    py_content = 'base = "https://api.example.com/v1/resource"'
    with patch("qabot.tools.api.list_files", return_value=["f.py"]):
        with patch("builtins.open", mock_open(read_data=py_content)):
            result = detect_api_endpoints("/proj")
    assert "https://api.example.com/v1/resource" in result


def test_detect_api_endpoints_deduplicates() -> None:
    py_content = 'a = "https://x.com"\nb = "https://x.com"'
    with patch("qabot.tools.api.list_files", return_value=["f.py"]):
        with patch("builtins.open", mock_open(read_data=py_content)):
            result = detect_api_endpoints("/proj")
    assert result.count("https://x.com") == 1


def test_test_api_endpoint_passed() -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    with patch("qabot.tools.api.httpx.request", return_value=mock_resp):
        result = call_endpoint("https://x.com")
    assert result["passed"] is True
    assert result["error"] == ""


def test_test_api_endpoint_wrong_status() -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    with patch("qabot.tools.api.httpx.request", return_value=mock_resp):
        result = call_endpoint("https://x.com", expected_status=200)
    assert result["passed"] is False
    assert result["status_code"] == 404


def test_test_api_endpoint_network_error() -> None:
    with patch("qabot.tools.api.httpx.request", side_effect=Exception("timeout")):
        result = call_endpoint("https://x.com")
    assert result["passed"] is False
    assert result["status_code"] == 0
    assert "timeout" in result["error"]


# ─── analyzer ────────────────────────────────────────────────────────────────


_BARE_EXCEPT = "try:\n    pass\nexcept:\n    pass\n"
_BROAD_EXCEPT = "try:\n    pass\nexcept Exception:\n    pass\n"
_SILENT_HANDLER = "try:\n    pass\nexcept ValueError:\n    pass\n"
_CLEAN_CODE = "x = 1\n"
_SYNTAX_ERROR_CODE = "def (\n"


def test_analyze_file_ast_bare_except() -> None:
    with patch("builtins.open", mock_open(read_data=_BARE_EXCEPT)):
        result = analyze_file_ast("f.py")
    assert any(f["category"] == "bare_except" for f in result)
    assert any(f["severity"] == "critical" for f in result)


def test_analyze_file_ast_broad_except() -> None:
    with patch("builtins.open", mock_open(read_data=_BROAD_EXCEPT)):
        result = analyze_file_ast("f.py")
    assert any(f["category"] == "broad_except" for f in result)


def test_analyze_file_ast_silent_handler() -> None:
    with patch("builtins.open", mock_open(read_data=_SILENT_HANDLER)):
        result = analyze_file_ast("f.py")
    assert any(f["category"] == "silent_exception" for f in result)


def test_analyze_file_ast_clean_code_returns_empty() -> None:
    with patch("builtins.open", mock_open(read_data=_CLEAN_CODE)):
        result = analyze_file_ast("f.py")
    assert result == []


def test_analyze_file_ast_syntax_error_returns_empty() -> None:
    with patch("builtins.open", mock_open(read_data=_SYNTAX_ERROR_CODE)):
        result = analyze_file_ast("bad.py")
    assert result == []


def test_analyze_project_ast_aggregates_findings() -> None:
    findings: list[dict] = [
        {
            "category": "bare_except",
            "severity": "critical",
            "file": "a.py",
            "line": 1,
            "description": "x",
        }
    ]
    with patch("qabot.tools.analyzer.list_files", return_value=["a.py", "b.py"]):
        with patch("qabot.tools.analyzer.analyze_file_ast", return_value=findings):
            result = analyze_project_ast("/proj")
    assert len(result) == 2


def test_analyze_project_ast_empty_project() -> None:
    with patch("qabot.tools.analyzer.list_files", return_value=[]):
        result = analyze_project_ast("/empty")
    assert result == []

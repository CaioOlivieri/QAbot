import ast
import contextlib
import json
import os
import re
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

from qabot import notify
from qabot.agent.exports import coverage_xml_has_lines, write_exports
from qabot.agent.llm import LLMProvider, get_provider
from qabot.agent.reconcile import (
    DEFAULT_DRE_WINDOW_DAYS,
    catchable,
    detection_breakdown,
    escape_rate,
    qa_observation_start,
    within_window,
)
from qabot.agent.report import (
    DEFAULT_THRESHOLDS,
    compute_scores,
    count_new_criticals,
    evaluate_gate,
    generate_report,
)
from qabot.state import current_commit, load_state, record_run, summarize_diff
from qabot.tools.analyzer import analyze_project_ast
from qabot.tools.api import detect_api_endpoints, test_api_endpoint
from qabot.tools.fs import list_files, read_file, write_file
from qabot.tools.github import fetch_production_bugs
from qabot.tools.runner import parse_coverage, parse_pytest_failures, run_command

_DEFAULT_MAX_ITERATIONS = 25


def _resolve_max_iterations() -> int:
    """Cap on the ReAct loop, overridable via ``QABOT_MAX_ITERATIONS``.

    The scheduled regression runs on the rate-limited Gemini free tier; a
    smaller cap lets a 429-throttled run still finish (and refresh the trend)
    inside the workflow's ``timeout-minutes`` ceiling. Falls back to the default
    on an unset, non-integer, or non-positive value.
    """
    raw = os.environ.get("QABOT_MAX_ITERATIONS")
    if raw is None:
        return _DEFAULT_MAX_ITERATIONS
    try:
        value = int(raw)
    except ValueError:
        return _DEFAULT_MAX_ITERATIONS
    return value if value > 0 else _DEFAULT_MAX_ITERATIONS


@dataclass(frozen=True)
class AgentState:
    project_path: str
    max_iterations: int = field(default_factory=_resolve_max_iterations)


@dataclass
class Findings:
    coverage_before: dict[str, float] = field(default_factory=dict)
    coverage_after: dict[str, float] = field(default_factory=dict)
    ast_bugs: list[dict[str, object]] = field(default_factory=list)
    dynamic_bugs: list[dict[str, object]] = field(default_factory=list)
    api_results: list[dict[str, object]] = field(default_factory=list)
    suspected_bugs: list[dict[str, object]] = field(default_factory=list)


def _call_llm(provider: LLMProvider, messages: list[dict[str, str]]) -> str:
    return provider.complete(messages)


_RETRY_429_SLEEP = 60
_RETRY_503_SLEEP = 10
_MAX_503_RETRIES = 5


def _call_llm_with_retry(provider: LLMProvider, messages: list[dict[str, str]]) -> str:
    unavailable_retries = 0
    while True:
        try:
            return _call_llm(provider, messages)
        except Exception as exc:
            exc_text = str(exc)
            if "429" in exc_text or "RESOURCE_EXHAUSTED" in exc_text:
                # A 429 means the model IS responding (just throttled), so it
                # ends any unavailability streak: reset so later 503s are only
                # counted when they are truly consecutive.
                unavailable_retries = 0
                print("Rate limited (429). Sleeping 60s before retry...")
                time.sleep(_RETRY_429_SLEEP)
            elif ("503" in exc_text or "UNAVAILABLE" in exc_text) and (
                unavailable_retries < _MAX_503_RETRIES
            ):
                unavailable_retries += 1
                print(
                    f"Model unavailable (503). "
                    f"Retry {unavailable_retries}/{_MAX_503_RETRIES} "
                    f"in {_RETRY_503_SLEEP}s..."
                )
                time.sleep(_RETRY_503_SLEEP)
            else:
                raise


_FENCE = re.compile(r"^```[a-zA-Z0-9]*\s*\n?(.*?)\n?```$", re.DOTALL)
_TRAILING_COMMA = re.compile(r",(\s*[}\]])")
_TEST_FILE = re.compile(r"^(test_.+\.py|.+_test\.py|conftest\.py)$")


def _strip_code_fence(text: str) -> str:
    match = _FENCE.match(text)
    return match.group(1).strip() if match else text


def _remove_trailing_commas(text: str) -> str:
    return _TRAILING_COMMA.sub(r"\1", text)


def _balanced_object(text: str, start: int) -> str | None:
    depth = 0
    in_string = False
    escaped = False
    for i in range(start, len(text)):
        char = text[i]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def _json_object_candidates(text: str) -> Iterator[str]:
    for start, char in enumerate(text):
        if char == "{":
            block = _balanced_object(text, start)
            if block is not None:
                yield block


def _try_loads(text: str) -> dict[str, object] | None:
    for strict in (True, False):
        try:
            parsed = json.loads(text, strict=strict)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def _parse_agent_json(text: str) -> dict[str, object]:
    stripped = text.strip()
    candidates = [stripped, _strip_code_fence(stripped)]
    candidates.extend(_json_object_candidates(stripped))
    for candidate in candidates:
        for variant in (candidate, _remove_trailing_commas(candidate)):
            parsed = _try_loads(variant)
            if parsed is not None:
                return parsed
    raise ValueError("no valid JSON object found in response")


def _ensure_dict(data: str | dict[str, object]) -> dict[str, object]:
    return data if isinstance(data, dict) else json.loads(data)


def _contain_in_root(path: str, project_path: str) -> str | None:
    """Absolute `path` if it resolves inside project_path, else None.

    Shared trust boundary for read and write tools: blocks absolute paths and
    `../` traversal that would escape the target project.
    """
    root = os.path.abspath(project_path)
    candidate = path if os.path.isabs(path) else os.path.join(root, path)
    target = os.path.abspath(candidate)
    within_root = target == root or target.startswith(root + os.sep)
    return target if within_root else None


def _resolve_write_path(path: str, project_path: str) -> str | None:
    target = _contain_in_root(path, project_path)
    if target is not None and _TEST_FILE.match(os.path.basename(target)):
        return target
    return None


def _resolve_read_path(path: str, project_path: str) -> str | None:
    return _contain_in_root(path, project_path)


def _dispatch(
    action: str, action_input: str | dict[str, object], project_path: str
) -> str:
    if action == "list_files":
        return str(list_files(action_input))
    if action == "read_file":
        target = _resolve_read_path(str(action_input), project_path)
        if target is None:
            return "Refused: read_file only reads files inside the project."
        return read_file(target)
    if action == "write_file":
        params = _ensure_dict(action_input)
        target = _resolve_write_path(str(params["path"]), project_path)
        if target is None:
            return (
                "Refused: write_file only creates test files "
                "(test_*.py, *_test.py, conftest.py) inside the project."
            )
        write_file(target, str(params["content"]))
        return "File written successfully."
    if action == "run_command":
        params = _ensure_dict(action_input)
        cwd = str(params.get("cwd", project_path))
        retcode, stdout, stderr = run_command(params["cmd"], cwd)
        return f"Return code: {retcode}\nStdout:\n{stdout}\nStderr:\n{stderr}"
    if action == "parse_coverage":
        data = parse_coverage(str(action_input))
        return str(data)
    if action == "detect_api_endpoints":
        result = detect_api_endpoints(str(action_input))
        return str(result)
    if action == "test_api_endpoint":
        params = _ensure_dict(action_input)
        result = test_api_endpoint(
            url=params["url"],
            method=params.get("method", "GET"),
            expected_status=params.get("expected_status", 200),
        )
        return str(result)
    if action == "parse_pytest_failures":
        result = parse_pytest_failures(str(action_input))
        return str(result)
    if action == "analyze_project_ast":
        inp = str(action_input) if action_input else project_path
        result = analyze_project_ast(inp)
        return str(result)
    if action == "report_suspected_bug":
        return "Suspected bug recorded."
    if action == "resolve_suspected_bug":
        return "Resolution recorded; outcome decided by the latest test run."
    return f"Unknown tool: {action}"


def _write_report(project_path: str, report_md: str) -> str:
    reports_dir = os.path.join(project_path, "reports")
    os.makedirs(reports_dir, exist_ok=True)
    report_path = os.path.join(reports_dir, "qa_report.md")
    with open(report_path, "w") as f:
        f.write(report_md)
    return report_path


def _resolve_suspicion(
    findings: Findings, params: dict[str, object], run_output: str
) -> str:
    status = "confirmed" if parse_pytest_failures(run_output) else "discarded"
    target_file = str(params.get("file", ""))
    target_line = int(params.get("line") or 0)
    for bug in findings.suspected_bugs:
        if bug["status"] != "suspected":
            continue
        if bug["file"] == target_file and bug["line"] == target_line:
            bug["status"] = status
            bug["evidence"] = run_output[:500] if status == "confirmed" else ""
            return status
    return "no matching suspicion"


def _accumulate_findings(
    action: str,
    action_input: str | dict[str, object],
    result: str,
    findings: Findings,
    last_run_output: str,
) -> str:
    if action == "parse_coverage":
        data = ast.literal_eval(result)
        if isinstance(data, dict):
            if not findings.coverage_before:
                findings.coverage_before = data
            else:
                findings.coverage_after = data
    elif action == "analyze_project_ast":
        data = ast.literal_eval(result)
        if isinstance(data, list):
            findings.ast_bugs.extend(data)
    elif action == "parse_pytest_failures":
        data = ast.literal_eval(result)
        if isinstance(data, list):
            findings.dynamic_bugs.extend(data)
    elif action == "test_api_endpoint":
        data = ast.literal_eval(result)
        if isinstance(data, dict):
            findings.api_results.append(data)
    elif action == "run_command":
        return result
    elif action == "report_suspected_bug":
        params = _ensure_dict(action_input)
        findings.suspected_bugs.append(
            {
                "file": str(params.get("file", "")),
                "line": int(params.get("line") or 0),
                "description": str(params.get("description", "")),
                "severity": str(params.get("severity", "warning")),
                "status": "suspected",
                "evidence": "",
            }
        )
    elif action == "resolve_suspected_bug":
        params = _ensure_dict(action_input)
        _resolve_suspicion(findings, params, last_run_output)
    return last_run_output


def _ledger_critical_summary(runs: list[dict[str, object]]) -> tuple[int, set[str]]:
    """Unique critical defects QAbot caught and every file it flagged (basenames)."""
    critical_fingerprints: set[str] = set()
    flagged_files: set[str] = set()
    for run in runs:
        for finding in run["findings"]:
            flagged_files.add(os.path.basename(str(finding["file"])))
            if finding["severity"] == "critical":
                critical_fingerprints.add(str(finding["fingerprint"]))
    return len(critical_fingerprints), flagged_files


def run_agent(project_path: str) -> str:
    load_dotenv(".env.keys")
    provider = get_provider()

    state = AgentState(project_path=project_path)
    findings = Findings()

    prior_runs = load_state(project_path)["runs"]
    assert isinstance(prior_runs, list)
    print(f"Defect ledger: {len(prior_runs)} prior run(s).")

    messages: list[dict[str, str]] = [
        {"role": "user", "content": f"Analyze the project at {project_path}"}
    ]

    final_answer: str | None = None
    consecutive_json_failures = 0
    last_run_output = ""

    for iteration in range(state.max_iterations):
        print(f"--- Iteration {iteration} ---")
        response_text = _call_llm_with_retry(provider, messages)
        messages.append({"role": "model", "content": response_text})

        try:
            parsed = _parse_agent_json(response_text)
            consecutive_json_failures = 0
        except ValueError:
            consecutive_json_failures += 1
            print("Invalid JSON response. Retrying.")
            if consecutive_json_failures >= 3:
                final_answer = "Aborted: 3 consecutive invalid JSON responses."
                break
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "Your previous response was not valid JSON. "
                        "Respond with a single JSON object only, no markdown "
                        "fences, no commentary. Escape newlines inside string "
                        "values as \\n."
                    ),
                }
            )
            continue

        thought: str | None = parsed.get("thought")
        action: str | None = parsed.get("action")
        if thought:
            print(f"Thought: {thought}")
        if action:
            print(f"Action: {action}")

        if "final_answer" in parsed:
            final_answer = parsed["final_answer"]
            break

        action_input: str | dict[str, object] = parsed.get("action_input", "")

        if action:
            try:
                result = _dispatch(action, action_input, state.project_path)
            except Exception as exc:
                result = f"Tool error in {action}: {exc}"
            else:
                last_run_output = _accumulate_findings(
                    action, action_input, result, findings, last_run_output
                )
            messages.append(
                {
                    "role": "user",
                    "content": f"Tool result for {action}: {result}",
                }
            )
        else:
            messages.append(
                {
                    "role": "user",
                    "content": "No action or final_answer found in JSON.",
                }
            )

    if final_answer is None:
        final_answer = "Max iterations reached without a final answer."

    coverage = findings.coverage_after or findings.coverage_before
    scores = compute_scores(
        findings.coverage_after,
        findings.ast_bugs,
        findings.dynamic_bugs,
        findings.api_results,
        findings.suspected_bugs,
    )
    new_state, diff = record_run(
        project_path,
        findings.ast_bugs,
        findings.dynamic_bugs,
        findings.suspected_bugs,
        coverage,
        commit_sha=current_commit(project_path),
        scores=scores,
    )
    runs = new_state["runs"]
    assert isinstance(runs, list)
    previous_quality = (
        runs[-2]["scores"]["quality"]
        if len(runs) >= 2 and isinstance(runs[-2].get("scores"), dict)
        else None
    )
    current_run = runs[-1]
    run_meta = {
        "run_id": current_run["run_id"],
        "timestamp": current_run["timestamp"],
        "commit_sha": current_run["commit_sha"],
        "thresholds": DEFAULT_THRESHOLDS,
    }

    production_bugs = fetch_production_bugs()
    reconciliation = None
    if production_bugs is not None:
        window_days = int(
            os.environ.get("QABOT_DRE_WINDOW_DAYS", DEFAULT_DRE_WINDOW_DAYS)
        )
        windowed = within_window(
            production_bugs, window_days, str(current_run["timestamp"])
        )
        critical_bugs = [b for b in windowed if b.severity == "critical"]
        # Temporal anchoring: only count criticals QA had a chance to catch
        # (reported at/after QA first analyzed a recorded commit).
        catchable_criticals = catchable(critical_bugs, qa_observation_start(runs))
        caught_criticals, flagged_files = _ledger_critical_summary(runs)
        reconciliation = {
            "escape": escape_rate(caught_criticals, len(catchable_criticals)),
            "breakdown": detection_breakdown(catchable_criticals, flagged_files),
            "window_days": window_days,
        }

    report_md = generate_report(
        project_path,
        findings.coverage_before,
        findings.coverage_after,
        findings.ast_bugs,
        findings.dynamic_bugs,
        findings.api_results,
        findings.suspected_bugs,
        diff=diff,
        run_meta=run_meta,
        previous_quality=previous_quality,
        reconciliation=reconciliation,
    )
    report_path = _write_report(project_path, report_md)
    print(f"Report saved to {report_path}")

    real_xml: str | None = None
    candidate = os.path.join(project_path, "coverage.xml")
    with contextlib.suppress(OSError):
        real_xml = Path(candidate).read_text()

    export_paths = write_exports(
        os.path.join(project_path, "reports"),
        coverage,
        findings.ast_bugs,
        findings.dynamic_bugs,
        findings.suspected_bugs,
        DEFAULT_THRESHOLDS,
        coverage_xml=real_xml
        if real_xml and coverage_xml_has_lines(real_xml)
        else None,
    )
    print(f"Exports: {', '.join(os.path.basename(p) for p in export_paths)}")
    print(summarize_diff(diff))

    verdict, reasons = evaluate_gate(scores["coverage"], diff, DEFAULT_THRESHOLDS)
    escape_pct = reconciliation["escape"].escape_rate if reconciliation else None
    notify.send(
        notify.Summary(
            project=project_path,
            verdict=verdict,
            reasons=reasons,
            quality=scores["quality"],
            previous_quality=previous_quality,
            new_criticals=count_new_criticals(diff),
            coverage=scores["coverage"],
            escape_rate=escape_pct,
        )
    )

    return final_answer

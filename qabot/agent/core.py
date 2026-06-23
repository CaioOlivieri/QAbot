import ast
import json
import os
import re
import time
from collections.abc import Iterator
from dataclasses import dataclass, field

from dotenv import load_dotenv
from google import genai
from google.genai import types

from qabot.agent.prompts import SYSTEM_PROMPT
from qabot.agent.report import generate_report
from qabot.tools.analyzer import analyze_project_ast
from qabot.tools.api import detect_api_endpoints, test_api_endpoint
from qabot.tools.fs import list_files, read_file, write_file
from qabot.tools.runner import parse_coverage, parse_pytest_failures, run_command


@dataclass(frozen=True)
class AgentState:
    project_path: str
    max_iterations: int = 25


@dataclass
class Findings:
    coverage_before: dict[str, float] = field(default_factory=dict)
    coverage_after: dict[str, float] = field(default_factory=dict)
    ast_bugs: list[dict[str, object]] = field(default_factory=list)
    dynamic_bugs: list[dict[str, object]] = field(default_factory=list)
    api_results: list[dict[str, object]] = field(default_factory=list)
    suspected_bugs: list[dict[str, object]] = field(default_factory=list)


def _call_llm(client: genai.Client, messages: list[dict[str, str]]) -> str:
    contents = [
        types.Content(role=m["role"], parts=[types.Part(text=m["content"])])
        for m in messages
    ]
    response = client.models.generate_content(
        model=os.environ.get("QABOT_MODEL", "gemini-2.5-flash-lite"),
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            response_mime_type="application/json",
        ),
    )
    return response.text


_RETRY_429_SLEEP = 60
_RETRY_503_SLEEP = 10
_MAX_503_RETRIES = 5


def _call_llm_with_retry(client: genai.Client, messages: list[dict[str, str]]) -> str:
    unavailable_retries = 0
    while True:
        try:
            return _call_llm(client, messages)
        except Exception as exc:
            exc_text = str(exc)
            if "429" in exc_text or "RESOURCE_EXHAUSTED" in exc_text:
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


def _resolve_write_path(path: str, project_path: str) -> str | None:
    root = os.path.abspath(project_path)
    candidate = path if os.path.isabs(path) else os.path.join(root, path)
    target = os.path.abspath(candidate)
    within_root = target == root or target.startswith(root + os.sep)
    if within_root and _TEST_FILE.match(os.path.basename(target)):
        return target
    return None


def _dispatch(
    action: str, action_input: str | dict[str, object], project_path: str
) -> str:
    if action == "list_files":
        return str(list_files(action_input))
    if action == "read_file":
        return read_file(action_input)
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


def run_agent(project_path: str) -> str:
    load_dotenv(".env.keys")
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    state = AgentState(project_path=project_path)
    findings = Findings()
    messages: list[dict[str, str]] = [
        {"role": "user", "content": f"Analyze the project at {project_path}"}
    ]

    final_answer: str | None = None
    consecutive_json_failures = 0
    last_run_output = ""

    for iteration in range(state.max_iterations):
        print(f"--- Iteration {iteration} ---")
        response_text = _call_llm_with_retry(client, messages)
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
            result = _dispatch(action, action_input, state.project_path)
            messages.append(
                {
                    "role": "user",
                    "content": f"Tool result for {action}: {result}",
                }
            )

            last_run_output = _accumulate_findings(
                action, action_input, result, findings, last_run_output
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

    report_md = generate_report(
        project_path,
        findings.coverage_before,
        findings.coverage_after,
        findings.ast_bugs,
        findings.dynamic_bugs,
        findings.api_results,
        findings.suspected_bugs,
    )
    report_path = _write_report(project_path, report_md)
    print(f"Report saved to {report_path}")

    return final_answer

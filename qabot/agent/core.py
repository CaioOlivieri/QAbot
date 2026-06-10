import ast
import json
import os
import time
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

TOOLS: dict[str, object] = {
    "list_files": list_files,
    "read_file": read_file,
    "write_file": write_file,
    "run_command": run_command,
    "parse_coverage": parse_coverage,
    "detect_api_endpoints": detect_api_endpoints,
    "test_api_endpoint": test_api_endpoint,
    "parse_pytest_failures": parse_pytest_failures,
    "analyze_project_ast": analyze_project_ast,
}


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


def _call_llm(client: genai.Client, messages: list[dict[str, str]]) -> str:
    contents = [
        types.Content(role=m["role"], parts=[types.Part(text=m["content"])])
        for m in messages
    ]
    response = client.models.generate_content(
        model="gemini-2.5-flash-lite",
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
        ),
    )
    return response.text


def _ensure_dict(data: str | dict[str, object]) -> dict[str, object]:
    return data if isinstance(data, dict) else json.loads(data)


def _dispatch(
    action: str, action_input: str | dict[str, object], project_path: str
) -> str:
    if action == "list_files":
        return str(list_files(action_input))
    if action == "read_file":
        return read_file(action_input)
    if action == "write_file":
        params = _ensure_dict(action_input)
        write_file(str(params["path"]), str(params["content"]))
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
    return f"Unknown tool: {action}"


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

    for iteration in range(state.max_iterations):
        print(f"--- Iteration {iteration} ---")
        while True:
            try:
                response_text = _call_llm(client, messages)
                break
            except Exception as exc:
                exc_text = str(exc)
                if "429" in exc_text or "RESOURCE_EXHAUSTED" in exc_text:
                    print("Rate limited. Sleeping 60s before retry...")
                    time.sleep(60)
                else:
                    raise
        messages.append({"role": "model", "content": response_text})

        cleaned = response_text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.removeprefix("```json").removeprefix("```")
            cleaned = cleaned.removesuffix("```")
            cleaned = cleaned.strip()

        try:
            parsed = json.loads(cleaned)
            consecutive_json_failures = 0
        except json.JSONDecodeError:
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
                        "Respond with a single JSON object only, "
                        "no markdown fences, no commentary."
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
    )
    os.makedirs("reports", exist_ok=True)
    with open("reports/qa_report.md", "w") as f:
        f.write(report_md)
    print("Report saved to reports/qa_report.md")

    return final_answer

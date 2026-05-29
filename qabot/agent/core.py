import json
import os
import time
from dataclasses import dataclass

from dotenv import load_dotenv
from google import genai
from google.genai import types

from qabot.agent.prompts import SYSTEM_PROMPT
from qabot.tools.api import detect_api_endpoints, test_api_endpoint
from qabot.tools.fs import list_files, read_file, write_file
from qabot.tools.runner import parse_coverage, run_command

TOOLS: dict[str, object] = {
    "list_files": list_files,
    "read_file": read_file,
    "write_file": write_file,
    "run_command": run_command,
    "parse_coverage": parse_coverage,
    "detect_api_endpoints": detect_api_endpoints,
    "test_api_endpoint": test_api_endpoint,
}


@dataclass(frozen=True)
class AgentState:
    project_path: str
    max_iterations: int = 10


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
    return f"Unknown tool: {action}"


def run_agent(project_path: str) -> str:
    load_dotenv(".env.keys")
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    state = AgentState(project_path=project_path)
    messages: list[dict[str, str]] = [
        {"role": "user", "content": f"Analyze the project at {project_path}"}
    ]

    for iteration in range(state.max_iterations):
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
        except json.JSONDecodeError:
            messages.append(
                {
                    "role": "user",
                    "content": (
                        f"Invalid JSON. Please respond with valid JSON only.\n"
                        f"Raw response: {response_text}"
                    ),
                }
            )
            continue

        thought: str | None = parsed.get("thought")
        action: str | None = parsed.get("action")
        print(f"--- Iteration {iteration} ---")
        if thought:
            print(f"Thought: {thought}")
        if action:
            print(f"Action: {action}")

        if "final_answer" in parsed:
            return parsed["final_answer"]

        action_input: str = parsed.get("action_input", "")

        if action:
            result = _dispatch(action, action_input, state.project_path)
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

    return "Max iterations reached without a final answer."

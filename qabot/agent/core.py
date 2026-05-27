import json
import os
from dataclasses import dataclass

from dotenv import load_dotenv
from google import genai
from google.genai import types

from qabot.agent.prompts import SYSTEM_PROMPT
from qabot.tools.fs import list_files, read_file, write_file
from qabot.tools.runner import parse_coverage, run_command

TOOLS: dict[str, object] = {
    "list_files": list_files,
    "read_file": read_file,
    "write_file": write_file,
    "run_command": run_command,
    "parse_coverage": parse_coverage,
}


@dataclass(frozen=True)
class AgentState:
    project_path: str
    max_iterations: int = 10


def _call_llm(client: genai.Client, messages: list[dict[str, str]]) -> str:
    contents = [
        {"role": m["role"], "parts": [m["content"]]} for m in messages
    ]
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
        ),
    )
    return response.text


def _dispatch(action: str, action_input: str, project_path: str) -> str:
    if action == "list_files":
        return str(list_files(action_input))
    if action == "read_file":
        return read_file(action_input)
    if action == "write_file":
        params = json.loads(action_input)
        write_file(params["path"], params["content"])
        return "File written successfully."
    if action == "run_command":
        params = json.loads(action_input)
        cwd = params.get("cwd", project_path)
        retcode, stdout, stderr = run_command(params["cmd"], cwd)
        return f"Return code: {retcode}\nStdout:\n{stdout}\nStderr:\n{stderr}"
    if action == "parse_coverage":
        data = parse_coverage(action_input)
        return str(data)
    return f"Unknown tool: {action}"


def run_agent(project_path: str) -> str:
    load_dotenv(".env.keys")
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    state = AgentState(project_path=project_path)
    messages: list[dict[str, str]] = [
        {"role": "user", "content": f"Analyze the project at {project_path}"}
    ]

    for iteration in range(state.max_iterations):
        response_text = _call_llm(client, messages)
        messages.append({"role": "model", "content": response_text})

        cleaned = response_text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.removeprefix("```json").removeprefix("```")
            cleaned = cleaned.removesuffix("```")
            cleaned = cleaned.strip()

        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            messages.append({
                "role": "user",
                "content": (
                    f"Invalid JSON. Please respond with valid JSON only.\n"
                    f"Raw response: {response_text}"
                ),
            })
            continue

        if "final_answer" in parsed:
            return parsed["final_answer"]

        action: str | None = parsed.get("action")
        action_input: str = parsed.get("action_input", "")

        if action:
            result = _dispatch(action, action_input, state.project_path)
            messages.append({
                "role": "user",
                "content": f"Tool result for {action}: {result}",
            })
        else:
            messages.append({
                "role": "user",
                "content": "No action or final_answer found in JSON.",
            })

    return "Max iterations reached without a final answer."

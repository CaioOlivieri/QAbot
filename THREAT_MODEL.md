# Threat Model

## Overview

QAbot is an autonomous LLM agent that analyzes arbitrary, potentially **UNTRUSTED** Python projects.
It reads files, writes test files, and runs shell commands on the machine it runs on — so it is security-sensitive by design.

## Trust boundary

| Zone | Examples |
|------|----------|
| **TRUSTED** | The runner/host machine, its OS, environment variables, and any secrets (e.g. `GEMINI_API_KEY`). |
| **UNTRUSTED** | The target project's source code and tests — which may contain prompt-injection payloads in docstrings, comments, or file names. |

The agent must never let untrusted input escape the project root, reach private network addresses, or run unbounded commands.

## Threats and controls

| Threat | Control | Code location |
|--------|---------|---------------|
| **Read exfiltration** — agent reads files outside the project | `read_file` is confined to the project root via `_contain_in_root` / `_resolve_read_path`; absolute paths and `../` traversal are refused. | `qabot/agent/core.py` |
| **Write outside scope** — agent writes non-test files or escapes the project | `_resolve_write_path` only allows test files (`test_*.py`, `*_test.py`, `conftest.py`) inside the project root. | `qabot/agent/core.py` |
| **SSRF / egress exfiltration** — agent makes outbound requests to private or internal hosts | `_ssrf_reason` resolves the host and refuses loopback, private (RFC1918), link-local (`169.254.0.0/16`, `fe80::/10`), reserved, multicast, and unspecified addresses. Outbound testing is opt-in via `QABOT_ALLOW_NETWORK` (off by default). | `qabot/tools/api.py` |
| **Hang / DoS** — a malicious project causes the agent to hang forever | `run_command` has a 120 s `DEFAULT_COMMAND_TIMEOUT` (server-side, not model-controllable; `TimeoutExpired` returns exit code 124). | `qabot/tools/runner.py` |
| **Runaway loop** — agent keeps iterating without converging | `AgentState.max_iterations = 25` caps the ReAct loop. | `qabot/agent/core.py` |
| **Secret hygiene** — API keys leak via tracked files | `.env.keys` is never tracked; `.gitignore` blocks `.env*`, `*.key`, `*.pem`, and `reports/`. | `.gitignore` |

## Residual risks

1. **`run_command` can execute ANY command by design** — the primary control is *operational*, not code. The timeout limits damage but does not prevent it.
2. **DNS rebinding** — the SSRF check resolves the host once, then `httpx` resolves again independently. A rebinding host could return a public IP at check time and a private IP at connection time. Pinning the resolved IP (passing it to `httpx` as the address) would fully close this gap.
3. **Prompt injection** can still steer the agent's reasoning within the allowed controls. A sufficiently crafted payload in source code may cause the agent to call allowed tools in unintended ways.

## Operational requirements

- Run QAbot **only** in an isolated / ephemeral sandbox or CI runner.
- **No production credentials** in the environment.
- **Restricted network egress** — keep API testing disabled (`QABOT_ALLOW_NETWORK` unset) unless the target project is trusted.
- Treat every output from the agent (reports, test files) as untrusted until reviewed.

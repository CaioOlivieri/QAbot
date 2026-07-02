# AGENT.md

Instructions for AI agents working on this codebase.

---

## What this project does

qabot is a CLI agent that analyzes Python projects, generates missing tests, detects bugs (static, dynamic, and execution-verified semantic), and produces a quality report. It reports bugs but never modifies the analyzed source.

```bash
python -m qabot <project_path>
```

---

## How to run

```bash
uv sync --extra dev
cp .env.example .env.keys  # add GEMINI_API_KEY (or another provider's key -- see README)
uv run python -m qabot <project_path>
```

```bash
uv run pytest
uv run ruff format .
uv run ruff check .
```

---

## Architecture

- `qabot/__main__.py` — CLI entrypoint (`--tier {regression,smoke}`, `--source`)
- `qabot/agent/core.py` — ReAct loop, tool dispatch, findings accumulation, semantic-suspicion gating (the `regression` tier)
- `qabot/agent/smoke.py` — deterministic, LLM-free PR gate: AST scan + the project's existing test suite + ledger diff (the `smoke` tier)
- `qabot/agent/llm.py` — provider-agnostic LLM layer (`QABOT_PROVIDER`: gemini, openai-compatible, anthropic)
- `qabot/agent/prompts.py` — LLM system prompt with tool descriptions
- `qabot/agent/report.py` — deterministic markdown report, gate scoring/thresholds, and `write_report` (shared by both tiers)
- `qabot/agent/exports.py` — machine-readable exports for CI: SARIF, JUnit XML, Cobertura coverage.xml
- `qabot/agent/reconcile.py` — pure DRE/escape-rate math and the time-based fallback anchor for production-bug reconciliation
- `qabot/state.py` — persistent defect ledger (`reports/qabot_state.json`) and run-over-run diff
- `qabot/notify.py` — Slack + GitHub PR comment notifications (opt-in by configuration presence)
- `qabot/tools/analyzer.py` — static AST bug scan
- `qabot/tools/api.py` — API endpoint detection/testing, opt-in and SSRF-guarded
- `qabot/tools/fs.py` — file system operations (list, read, write)
- `qabot/tools/runner.py` — command execution, coverage parsing, pytest failure classification
- `qabot/tools/github.py` — production-bug adapter: GitHub issues → `reconcile.ProductionBug`
- `qabot/tools/git_blame.py` — SZZ bug-introducing-commit provenance (git-local, opt-in)

(`__init__.py` files are empty package markers, omitted above.)

---

## Rules

- Update this file before changing architecture
- Type hints on every function — no exceptions
- No obvious comments — names and types explain the code
- Pure functions where possible
- Never read or expose `.env.keys`
- Tests live in `tests/` — mirror the source structure

---

## Security model

qabot runs on the user's machine and acts on a *trusted local* project. The
full threat model (trust boundary, every threat and its control, residual
risks) lives in [`THREAT_MODEL.md`](THREAT_MODEL.md) — read it before
touching any security-relevant code; do not let this summary drift from it:

- `run_command` (`tools/runner.py`) executes shell commands chosen by the LLM,
  with no allowlist or sandbox and a 120s timeout. This is intentional — the
  agent needs to run `pytest`, `ruff`, etc. — but it means a prompt-injected or
  mistaken model can run arbitrary commands (bounded by the timeout). Only
  point qabot at projects you trust.
- `read_file`/`write_file` are confined to the project root
  (`_contain_in_root` / `_resolve_read_path`); `write_file` additionally
  refuses any path that is not a test file (`test_*.py`, `*_test.py`,
  `conftest.py`), so the agent cannot modify analyzed source even if it tries.
- `test_api_endpoint` is **opt-in** (`QABOT_ALLOW_NETWORK`, off by default) and
  SSRF-guarded when enabled: it resolves the target host once, refuses
  non-public addresses (private/loopback/link-local/reserved/multicast), and
  pins the connection to that validated IP so DNS rebinding cannot swap in a
  private address between the check and the connect (`tools/api.py`).
- `AgentState.max_iterations` (default 25, `QABOT_MAX_ITERATIONS`) caps the
  ReAct loop so a non-converging run cannot iterate forever.
- Never read or expose `.env.keys` (already git-ignored) — this applies to
  every provider key (`QABOT_API_KEY` and friends), not just Gemini's.

---

## Knowledge base

This repo maintains a wiki in `./wiki/` (LLM-Wiki format). Before any architecture
change, agents must read:
1. `wiki/_estado-de-integracao.md` — single source of truth on what is wired
2. `wiki/_schema.md` — discipline rules for this wiki

Discipline rule (QAbot): only assert test/coverage/behavior based on real
execution output saved in `wiki/raw/` — never by inference.
When learning something durable, do ingest: update the page and `_indice.md`.

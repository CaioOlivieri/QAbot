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
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env.keys  # add GEMINI_API_KEY
python -m qabot <project_path>
```

```bash
pytest
ruff format .
ruff check .
```

---

## Architecture

- `qabot/__main__.py` — CLI entrypoint
- `qabot/agent/core.py` — ReAct loop, tool dispatch, findings accumulation, semantic-suspicion gating
- `qabot/agent/prompts.py` — LLM system prompt with tool descriptions
- `qabot/agent/report.py` — deterministic markdown report (incl. semantic & for-review sections)
- `qabot/tools/api.py` — API endpoint detection and testing
- `qabot/tools/analyzer.py` — static AST bug scan
- `qabot/tools/fs.py` — file system operations (list, read, write)
- `qabot/tools/runner.py` — command execution, coverage parsing, pytest failure classification

---

## Rules

- Update this file before changing architecture
- Type hints on every function — no exceptions
- No obvious comments — names and types explain the code
- Pure functions where possible
- Never read or expose `.env.keys`
- Tests live in `tests/` — mirror the source structure

---

## Knowledge base

This repo maintains a wiki in `./wiki/` (LLM-Wiki format). Before any architecture
change, agents must read:
1. `wiki/_estado-de-integracao.md` — single source of truth on what is wired
2. `wiki/_schema.md` — discipline rules for this wiki

Discipline rule (QAbot): only assert test/coverage/behavior based on real
execution output saved in `wiki/raw/` — never by inference.
When learning something durable, do ingest: update the page and `_indice.md`.

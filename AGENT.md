# AGENT.md

Instructions for AI agents working on this codebase.

---

## What this project does

qabot is a CLI agent that analyzes Python projects, generates missing tests, detects bugs, and produces a quality report.

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
pytest        # run tests
ruff check .  # lint
```

---

## Architecture

- `tools/api.py` — `detect_api_endpoints`, `test_api_endpoint`

---

## Rules

- Update this file before changing architecture
- Type hints on every function — no exceptions
- No obvious comments — names and types explain the code
- Pure functions where possible
- Never read or expose `.env.keys`
- Tests live in `tests/` — mirror the source structure

---

## Pending (in order)

1. `qabot/agent/report.py` — markdown report generation
2. Bug detection — static (LLM analysis) + dynamic (pytest failures)
3. `tests/test_tools.py` and `tests/test_agent.py`
4. GitHub Actions CI
5. `tools/api.py` — api testing
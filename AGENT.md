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
pytest
ruff format .
ruff check .
```

---

## Architecture

- `tools/api.py` — `detect_api_endpoints`, `test_api_endpoint`
- `tools/analyzer.py` — # static analysis — AST + LLM semantic

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

## Base de conhecimento (wiki)
Este repo mantém uma wiki em ./wiki/ (padrão LLM-Wiki). Antes de agir:
1. Leia wiki/_schema.md e wiki/_estado-de-integracao.md.
2. Carregue só as páginas relevantes — nunca a wiki inteira.
3. Conhecimento transversal (Python, B2G, setup WSL) fica na wiki global ~/wiki.

Regra de disciplina (QAbot): só afirme resultado de teste/cobertura/comportamento
com base em saída real de execução salva em raw/ — nunca por inferência.
Ao aprender algo durável, faça ingest: atualize a página e o _indice.md.

NOTA: AGENT.md e README.md hoje divergem do código (ver _estado-de-integracao.md).
Corrija-os junto da Layer 0.

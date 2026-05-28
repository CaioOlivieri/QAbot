# QAbot

AI agent for automated QA on Python projects.

Given a local repository, qabot analyzes test coverage, generates missing tests, detects critical bugs, and produces a quality report — all autonomously.

---

## What it does

1. Lists Python files and existing tests in the project
2. Runs `pytest --cov` to get current coverage per module
3. Identifies modules below 80% coverage
4. Reads modules with gaps and existing tests for context
5. Generates pytest unit tests for the gaps
6. Writes test files to disk
7. Runs `pytest --cov` again to validate coverage
8. Detects critical bugs — static analysis via LLM + dynamic via pytest failures
9. Produces a markdown report with before/after coverage, bugs found, and suggestions

---

## Demo

Running qabot against [AlertaVida](https://github.com/CaioOlivieri/AlertaVida), a real disaster monitoring system:

```bash
python -m qabot ~/Projetos/AlertaVida
```

```
--- Iteration 0 ---
Thought: I need to start by listing the files to understand the project structure.
Action: list_files

--- Iteration 1 ---
Thought: I have the structure. Running pytest --cov to get baseline coverage.
Action: run_command

--- Iteration 2 ---
Thought: Coverage report obtained. Identifying modules below 80%.
Action: parse_coverage
...
```

---

## Installation

**Requirements:** Python 3.13+

```bash
git clone https://github.com/CaioOlivieri/QAbot.git
cd QAbot

python3 -m venv .venv
source .venv/bin/activate

pip install -e ".[dev]"

cp .env.example .env.keys
# edit .env.keys and add your GEMINI_API_KEY
# get your key at: https://aistudio.google.com/apikey
```

---

## Usage

```bash
python -m qabot <project_path>
```

---

## Architecture

```
qabot/
├── __main__.py        # CLI entrypoint
├── agent/
│   ├── core.py        # ReAct loop
│   ├── prompts.py     # QA specialist system prompt
│   └── report.py      # markdown report generation
└── tools/
    ├── fs.py          # list_files, read_file, write_file
    └── runner.py      # run_command, parse_coverage
```

### How it works

The agent runs a **ReAct loop** (Reason + Act): at each iteration it reasons about what to do, calls a tool, observes the result, and repeats until it reaches a final answer or the iteration limit.

### Design decisions

**No framework.** The ReAct loop is implemented from scratch — no LangChain, no LangGraph, no smolagents. Every line is intentional and explainable.

**Gemini 2.5 Flash Lite.** Free tier with enough quota for development and demos. Swappable via environment variable.

**CLI first.** No UI. Designed for CI/CD integration — pipe it, script it, automate it.

**Bug detection in two layers.** Static analysis catches silent exceptions and unhandled edge cases before tests run. Dynamic analysis classifies pytest failures by severity.

---

## Success criteria

- Final coverage > 80% on the target project
- 100% of generated tests passing without manual intervention
- 100% of critical bugs caught before production
- Markdown report generated automatically

---

## Development

```bash
pytest          # run tests
ruff check .    # lint
```

---

## License

MIT
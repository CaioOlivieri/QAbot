# QAbot

[![CI](https://github.com/CaioOlivieri/QAbot/actions/workflows/ci.yml/badge.svg)](https://github.com/CaioOlivieri/QAbot/actions/workflows/ci.yml) [![codecov](https://codecov.io/gh/CaioOlivieri/QAbot/graph/badge.svg)](https://codecov.io/gh/CaioOlivieri/QAbot)

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
8. Detects critical bugs — static (AST) + dynamic (pytest failures) + semantic (LLM hypotheses confirmed by execution)
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

Or, with [uv](https://github.com/astral-sh/uv) — uses the committed `uv.lock`
for a reproducible install:

```bash
uv sync
cp .env.example .env.keys  # then add your GEMINI_API_KEY
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
    ├── api.py          # API endpoint detection and testing
    ├── analyzer.py     # static AST bug scanner
    ├── fs.py           # list_files, read_file, write_file
    └── runner.py       # run_command, parse_coverage, parse_pytest_failures
```

### How it works

The agent runs a **ReAct loop** (Reason + Act): at each iteration it reasons about what to do, calls a tool, observes the result, and repeats until it reaches a final answer or the iteration limit.

### Design decisions

**No framework.** The ReAct loop is implemented from scratch — no LangChain, no LangGraph, no smolagents. Every line is intentional and explainable.

**Gemini 2.5 Flash Lite.** Free tier with enough quota for development and demos. Swappable via the `QABOT_MODEL` environment variable (default `gemini-2.5-flash-lite`) — e.g. `QABOT_MODEL=gemini-2.5-flash`.

**CLI first.** No UI. Designed for CI/CD integration — pipe it, script it, automate it.

**Bug detection in three layers.** Static analysis (AST) catches silent exceptions and unhandled edge cases before tests run. Dynamic analysis classifies pytest failures by severity. Semantic analysis lets the LLM raise a bug *hypothesis* (off-by-one, inverted condition, code that contradicts its docstring) — reported as confirmed only when a generated test actually fails for it; unverified suspicions are listed separately and never affect the score. The agent reports bugs but never modifies the analyzed source.

---

## Success criteria

- Final coverage > 80% on the target project
- 100% of generated tests passing without manual intervention
- 100% of critical bugs caught before production
- Markdown report generated automatically

---

## Development

```bash
pytest
ruff format .
ruff check .
```

---

## Production reconciliation (DRE)

QAbot can measure the **critical defect escape rate** and its inverse, **Defect
Removal Efficiency (DRE)** — of the critical bugs your project hit, how many
escaped to production versus were caught by QA. It is **opt-in** and only **reads**
your issue tracker; left unset, the report simply omits the metric.

To enable it on **your** project:

1. **Point it at the repo** whose GitHub issues track production bugs:
   ```bash
   export QABOT_PROD_REPO=your-org/your-repo
   ```
2. **(Optional) labels.** By default QAbot reads issues labeled `bug` or
   `production` and treats `critical`/`blocker`/`p0`/`sev1` as critical:
   ```bash
   export QABOT_PROD_LABELS=bug,production
   export QABOT_CRITICAL_LABELS=critical,blocker,p0,sev1
   ```
3. **(Optional) token.** Public repos work with no token (GitHub allows ~60
   requests/hour). For private repos or a higher limit, create a **fine-grained
   Personal Access Token** with **Issues: Read-only** on that repo:
   ```bash
   export GITHUB_TOKEN=your_read_only_token
   ```
   The token is read from the environment only — never written, logged, or
   committed — and can be revoked any time in GitHub settings.
4. **(Optional) window.** DRE is measured over a trailing window (default **90
   days**, per Capers Jones; ISBSG uses 30):
   ```bash
   export QABOT_DRE_WINDOW_DAYS=90
   ```

Run QAbot as usual — the report gains a **Critical Defect Escape Rate (DRE)**
section. QAbot only reads issues from `api.github.com`; it never writes to your
repo or account.

> DRE = caught / (caught + escaped); a production defect is an escape by definition
> (Capers Jones, *The Economics of Software Quality*, 2011). The metric is scoped to
> the defects QAbot could reconcile and states its confounders in the report.

---

## Security

QAbot treats the target project as **untrusted** — it reads files, writes test files, and executes shell commands inside a sandboxed environment. File access is confined to the project root, writes are restricted to test files, outbound network requests are opt-in (`QABOT_ALLOW_NETWORK=1`, disabled by default), and all shell commands have a 120-second timeout. Always run QAbot in an isolated CI runner or ephemeral container with no production credentials. For full details, see [THREAT_MODEL.md](THREAT_MODEL.md).

---

## License

MIT
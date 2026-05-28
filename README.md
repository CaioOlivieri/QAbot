# QAbot

AI agent for automated QA on Python projects.

Given a local repository, qabot analyzes test coverage, generates missing tests, and produces a quality report — all autonomously.

## What it does

1. Lists Python files and existing tests in the project
2. Runs `pytest --cov` to get current coverage per module
3. Identifies modules below 80% coverage
4. Generates pytest unit tests for the gaps
5. Writes test files to disk
6. Runs `pytest --cov` again to validate coverage
7. Produces a markdown report with before/after coverage and findings
8. Detects critical bugs before they reach production

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

## Installation

**Requirements:** Python 3.13+, [uv](https://docs.astral.sh/uv/) or pip

```bash
# Clone the repository
git clone https://github.com/CaioOlivieri/QAbot.git
cd QAbot

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # Linux/macOS

# Install dependencies
pip install -e ".[dev]"

# Configure API key
cp .env.example .env.keys
# Edit .env.keys and add your GEMINI_API_KEY
# Get your key at: https://aistudio.google.com/apikey
```

## Usage

```bash
python -m qabot <project_path>
```

```bash
# Example
python -m qabot ~/Projetos/AlertaVida
```

## Architecture

```
qabot/
├── __main__.py        # CLI entrypoint
├── agent/
│   ├── core.py        # ReAct loop
│   ├── prompts.py     # QA specialist system prompt
│   └── report.py      # Markdown report generation
└── tools/
    ├── fs.py          # list_files, read_file, write_file
    └── runner.py      # run_command, parse_coverage
```

The agent runs a **ReAct loop** (Reason + Act): at each iteration it reasons about what to do, calls a tool, observes the result, and repeats until it reaches a final answer or the iteration limit.

**LLM:** Gemini 2.5 Flash Lite via Google AI Studio (free tier)  
**Agent pattern:** minimal custom ReAct — no framework  
**Stack:** Python 3.13, pytest, pytest-cov, ruff, python-dotenv

## Success criteria

- Final coverage > 80% on the target project
- 100% of generated tests passing without manual intervention
- Markdown report generated automatically
- 100% of critical bugs caught before production

## Development

```bash
# Run tests
pytest

# Lint
ruff check .
```

## License

MIT
.PHONY: run test lint

run:
	source .venv/bin/activate && python -m qabot

test:
	source .venv/bin/activate && pytest tests/ -v --cov=qabot

lint:
	source .venv/bin/activate && ruff format . && ruff check .

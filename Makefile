.PHONY: run test format lint

run:
	source .venv/bin/activate && python -m qabot $(ARGS)

test:
	source .venv/bin/activate && pytest tests/ -v --cov=qabot

format:
	source .venv/bin/activate && ruff format .

lint:
	source .venv/bin/activate && ruff format --check . && ruff check .

.PHONY: run test format lint

run:
	uv run python -m qabot $(ARGS)

test:
	uv run pytest -v

format:
	uv run ruff format .

lint:
	uv run ruff format --check . && uv run ruff check .

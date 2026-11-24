export UV_LOCKED := "1"

fix:
    uv run ruff check --fix src tests
    uv run ruff format src tests

check:
    uv run ruff format --check src tests
    uv run ruff check src tests
    uv run ty check

test:
    uv run python -m unittest discover -s tests -v

status:
    uv run math-books list

ci: check test

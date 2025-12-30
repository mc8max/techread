.PHONY: lint test fmt

lint:
	ruff check .

test:
	pytest

fmt:
	black .
	isort .

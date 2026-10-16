.PHONY: setup run test lint migrate reset-demo smoke help

PYTHON ?= python

help:
	@echo "Available commands:"
	@echo "  make setup       - Install dependencies"
	@echo "  make migrate     - Run database migrations"
	@echo "  make run         - Run the development server"
	@echo "  make test        - Run tests via pytest"
	@echo "  make lint        - Run ruff linter"
	@echo "  make reset-demo  - Reset demo data and clock (requires DEMO_MODE=1)"
	@echo "  make smoke       - Run the smoke test against local server"

setup:
	$(PYTHON) -m pip install -r requirements-dev.txt

migrate:
	$(PYTHON) manage.py migrate

run:
	$(PYTHON) manage.py runserver 127.0.0.1:8000

test:
	pytest -q

lint:
	ruff check .

reset-demo:
	$(PYTHON) manage.py reset_demo --yes

smoke:
	$(PYTHON) scripts/smoke_test.py --base-url http://127.0.0.1:8000

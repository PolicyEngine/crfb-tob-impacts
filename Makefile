.PHONY: all install data dashboard dashboard-dev paper site test lint format clean help

all: install dashboard paper

install:
	@echo "Installing Python package and dashboard dependencies..."
	uv venv --python 3.13 || true
	uv pip install -e .
	uv pip install -e .[dev]
	cd dashboard && bun install

data:
	@echo "Generating policy impact data..."
	. .venv/bin/activate && python scripts/generate_policy_impacts.py

dashboard:
	@echo "Building Next dashboard..."
	cd dashboard && bun run build

dashboard-dev:
	@echo "Starting Next dashboard..."
	cd dashboard && bun run dev

paper:
	@echo "Rendering Quarto paper..."
	quarto render paper/index.qmd --to html

site:
	@echo "Building combined Vercel site..."
	./scripts/build_vercel_site.sh

test:
	@echo "Running Python tests..."
	pytest tests/ -v --cov=src --cov-report=term-missing

lint:
	@echo "Linting Python and dashboard code..."
	ruff format --check src/ tests/ scripts/
	cd dashboard && bun run lint

format:
	@echo "Formatting Python and dashboard code..."
	ruff format src/ tests/ scripts/
	cd dashboard && bun run lint -- --fix

clean:
	@echo "Cleaning generated files..."
	rm -rf .vercel-site/
	rm -rf dashboard/out dashboard/.next
	rm -rf paper/_build paper/index_files paper/index.pdf
	rm -rf data/*.csv
	rm -rf __pycache__/ src/__pycache__/ tests/__pycache__/
	rm -rf .pytest_cache/ .coverage htmlcov/
	find . -type f -name "*.pyc" -delete
	find . -type d -name ".ipynb_checkpoints" -exec rm -rf {} +

help:
	@echo "Available targets:"
	@echo "  install       - Install Python package and dashboard dependencies"
	@echo "  data          - Generate policy impact data"
	@echo "  dashboard     - Build the Next dashboard"
	@echo "  dashboard-dev - Run the Next dashboard locally"
	@echo "  paper         - Render the Quarto paper HTML"
	@echo "  site          - Build dashboard at / and paper at /paper/"
	@echo "  test          - Run Python tests"
	@echo "  lint          - Check formatting/lint"
	@echo "  format        - Auto-format code"
	@echo "  clean         - Remove generated files"

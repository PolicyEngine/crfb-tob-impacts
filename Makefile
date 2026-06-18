.PHONY: all install panel data dashboard dashboard-dev paper site test lint format clean help

all: install dashboard paper

panel:
	@echo "The old aggregate-only panel launcher is archived and fail-closed."
	@echo "Use modal_batch/reform_full_h5.py::submit_reform_full_h5 after ledger approval."
	@exit 1

install:
	@echo "Installing Python package and dashboard dependencies..."
	uv venv --python 3.13 || true
	uv pip install -e .
	uv pip install -e .[dev]
	cd dashboard && bun install

data:
	@echo "Reform data is produced from durable reform_full_h5 artifacts."
	@echo "Use scripts/aggregate_reform_full_h5_results.py only after full-H5 cells exist."

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
	@echo "  panel         - Archived fail-closed legacy aggregate launcher"
	@echo "  data          - Explain current full-H5 data assembly"
	@echo "  dashboard     - Build the Next dashboard"
	@echo "  dashboard-dev - Run the Next dashboard locally"
	@echo "  paper         - Render the Quarto paper HTML"
	@echo "  site          - Build dashboard at / and paper at /paper/"
	@echo "  test          - Run Python tests"
	@echo "  lint          - Check formatting/lint"
	@echo "  format        - Auto-format code"
	@echo "  clean         - Remove generated files"

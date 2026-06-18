.PHONY: all install panel data dashboard dashboard-dev paper site test lint format clean help

all: install dashboard paper

panel:
	@echo "Building full reform panel on Modal (resumable: builds missing"
	@echo "baselines, self-pipelines reform scoring per year, assembles panel)..."
	modal run --detach modal_batch/run_panel.py $(ARGS)

install:
	@echo "Installing Python package and dashboard dependencies..."
	uv venv --python 3.13 || true
	uv pip install -e .
	uv pip install -e .[dev]
	cd dashboard && bun install

data:
	@echo "Reform data is produced by the Modal pipeline, not a single script:"
	@echo "  1. make panel   (build baselines + score reforms on Modal)"
	@echo "  2. python scripts/assemble_reform_panel.py   (static + behavioral multipliers)"
	@echo "  3. python scripts/build_dashboard_results.py (dashboard results.csv + decomposition)"
	@echo "See modal_batch/run_panel.py for the full flow."

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
	@echo "  panel         - Build full reform panel on Modal (resumable; ARGS='--years ... --reforms ...')"
	@echo "  data          - Generate policy impact data"
	@echo "  dashboard     - Build the Next dashboard"
	@echo "  dashboard-dev - Run the Next dashboard locally"
	@echo "  paper         - Render the Quarto paper HTML"
	@echo "  site          - Build dashboard at / and paper at /paper/"
	@echo "  test          - Run Python tests"
	@echo "  lint          - Check formatting/lint"
	@echo "  format        - Auto-format code"
	@echo "  clean         - Remove generated files"

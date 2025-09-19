.PHONY: all install data book dashboard test clean help

# Default target
all: install data book dashboard

# Install Python and Node dependencies
install: install-python install-node

install-python:
	@echo "Installing Python dependencies..."
	pip install --upgrade pip
	pip install -r requirements.txt

install-node:
	@echo "Installing Node dependencies..."
	cd policy-impact-dashboard && npm ci

# Generate policy impact data
data:
	@echo "Generating policy impact data..."
	python generate_policy_impacts.py

data-quick:
	@echo "Generating fiscal data only (skipping household)..."
	python generate_policy_impacts.py --skip-household

# Build Jupyter Book documentation
book:
	@echo "Building Jupyter Book..."
	cd jupyterbook && jupyter-book build .
	@echo "Book built at: jupyterbook/_build/html/"

book-clean:
	@echo "Cleaning Jupyter Book build..."
	cd jupyterbook && jupyter-book clean .

# Build and run React dashboard
dashboard:
	@echo "Building React dashboard..."
	cd policy-impact-dashboard && npm run build

dashboard-dev:
	@echo "Starting React dashboard in development mode..."
	cd policy-impact-dashboard && npm start

# Run tests
test: test-python test-react

test-python:
	@echo "Running Python tests..."
	pytest tests/ -v --cov=src --cov-report=term-missing

test-react:
	@echo "Running React tests..."
	cd policy-impact-dashboard && npm test -- --watchAll=false

# Lint and format code
lint: lint-python lint-react

lint-python:
	@echo "Linting Python code..."
	black src/ tests/ generate_policy_impacts.py --check
	pylint src/

lint-react:
	@echo "Linting React code..."
	cd policy-impact-dashboard && npm run lint

format: format-python format-react

format-python:
	@echo "Formatting Python code..."
	black src/ tests/ generate_policy_impacts.py

format-react:
	@echo "Formatting React code..."
	cd policy-impact-dashboard && npm run lint -- --fix && npx prettier --write .

# Clean generated files
clean:
	@echo "Cleaning generated files..."
	rm -rf jupyterbook/_build/
	rm -rf policy-impact-dashboard/build/
	rm -rf data/*.csv
	rm -rf __pycache__/ src/__pycache__/ tests/__pycache__/
	rm -rf .pytest_cache/
	rm -rf .coverage
	rm -rf htmlcov/
	find . -type f -name "*.pyc" -delete
	find . -type d -name ".ipynb_checkpoints" -exec rm -rf {} +

# CI/CD commands
ci: install lint test data book dashboard
	@echo "CI pipeline complete!"

# Deployment preparation
deploy-prep: clean install data book dashboard
	@echo "Deployment preparation complete!"

# Help command
help:
	@echo "Available targets:"
	@echo "  all           - Install deps, generate data, build book & dashboard (default)"
	@echo "  install       - Install all dependencies (Python and Node)"
	@echo "  data          - Generate all policy impact data"
	@echo "  data-quick    - Generate fiscal data only (skip household)"
	@echo "  book          - Build Jupyter Book documentation"
	@echo "  dashboard     - Build React dashboard for production"
	@echo "  dashboard-dev - Run React dashboard in development mode"
	@echo "  test          - Run all tests (Python and React)"
	@echo "  lint          - Check code formatting"
	@echo "  format        - Auto-format code"
	@echo "  clean         - Remove all generated files"
	@echo "  ci            - Run full CI pipeline"
	@echo "  help          - Show this help message"
# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This repository contains a Social Security taxation reform analysis project with two main components:
1. **Jupyter Book documentation** - Research report and analysis using MyST-NB (Jupyter Book 2.0)
2. **React dashboard** - Interactive policy impact visualization tool

## Build and Development Commands

### Setup with uv (Python 3.13)
```bash
# Install uv if needed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment and install dependencies
uv venv --python 3.13
source .venv/bin/activate
uv pip install -e .
uv pip install -e .[dev]  # For development dependencies
```

### Jupyter Book Documentation
```bash
# Build the Jupyter Book (uses MyST-NB)
source .venv/bin/activate
cd jupyterbook
jupyter-book build .

# The built documentation will be in jupyterbook/_build/html/
```

### React Dashboard
```bash
# Navigate to the dashboard directory
cd policy-impact-dashboard

# Install dependencies
npm install

# Development server (runs on http://localhost:3000)
npm start

# Run tests
npm test

# Production build
npm run build
```

## High-Level Architecture

### Documentation Structure (Jupyter Book)
The Jupyter Book uses MyST-NB and contains:
- **intro.md** - Landing page and overview
- **policy-options.md** - Detailed policy proposals
- **prior-research.md** - Literature review
- **methodology.ipynb** - Technical analysis methods
- **policy-impacts.md** - Aggregate fiscal impacts
- **household-impacts.ipynb** - Distributional analysis with animated visualizations across years 2026-2035
- **bibliography.md** - References

Key configuration:
- `_config.yml` - MyST-NB configuration with forced notebook execution
- `_toc.yml` - Table of contents structure
- `hide_code_cells.py` - Custom script for hiding implementation details

### Dashboard Application
The React dashboard (`policy-impact-dashboard/`) provides interactive policy visualization:

**Core Components:**
- `PolicySelector` - Dropdown interface for policy selection with credit value options
- `ImpactDisplay` - Visualization of 10-year budgetary impacts
- `csvLoader` - Utility for loading and processing policy impact CSV data

**Data Flow:**
1. CSV data (`policy_impacts.csv`) contains pre-computed policy impacts
2. App loads CSV on mount and processes into policy options
3. User selects policy → displays corresponding impact data
4. Supports policies with variable credit values (e.g., $100-$900 refundable credits)

### Data Integration
- Analysis notebooks generate `policy_impacts_results.csv` with fiscal estimates
- Dashboard consumes this CSV for visualization
- Both components share the same underlying PolicyEngine analysis
- Household impacts notebook generates multi-year data (2026-2035) with animated visualizations using Plotly animation frames

## Key Development Patterns

### Jupyter Book
- Uses MyST-NB (not legacy Jupyter Book 1.x)
- Notebooks execute on build with 600-second timeout
- Custom CSS in `_static/custom.css`
- Code cells can be toggled with show/hide prompts

### React Dashboard
- TypeScript with functional components
- No external state management (local state only)
- CSV parsing with PapaParse library
- Dynamic policy data based on CSV content

## Testing

### Dashboard Tests
```bash
cd policy-impact-dashboard
npm test          # Run all tests
npm test -- --coverage  # With coverage report
```

Tests use React Testing Library and focus on component rendering and data handling.
# GEMINI.md

This file provides context and instructions for AI agents working on the `crfb-tob-impacts` project.

## Project Overview

**Project Name:** `crfb-tob-impacts`
**Purpose:** Analysis of Social Security taxation reforms using PolicyEngine.
**Components:**
1.  **Python Analysis:** Core logic (`src/`) and scripts (`scripts/`) to calculate fiscal and household impacts.
2.  **Documentation:** A Jupyter Book (`jupyterbook/`) research report.
3.  **Dashboard:** A React-based visualization tool (`policy-impact-dashboard/`).

## Technical Stack

*   **Language:** Python 3.13 (Analysis), TypeScript/React (Dashboard)
*   **Dependency Management:** `uv` (Python), `npm` (Node.js)
*   **Simulation Engine:** `policyengine-us` (v1.398.0+)
*   **Documentation:** Jupyter Book (MyST-NB)
*   **Visualization:** Plotly (Python), Recharts/custom (React)

## Key Directories

*   `src/`: Core Python modules (`reforms.py`, `impact_calculator.py`).
*   `scripts/`: Data generation and utility scripts.
*   `jupyterbook/`: Source for the documentation site.
*   `policy-impact-dashboard/`: React application source.
*   `data/`: Generated CSV data files used by the dashboard and notebooks.
*   `tests/`: Python test suite.

## Development Workflows

### 1. Setup
```bash
# Install Python dependencies
uv venv --python 3.13
source .venv/bin/activate
uv pip install -e .
uv pip install -e .[dev]

# Install Node dependencies
cd policy-impact-dashboard
npm ci
```

### 2. Data Generation
**Critical Step:** The dashboard and notebooks rely on generated data.
```bash
# Full generation (can take 15-30 mins)
python scripts/generate_policy_impacts.py

# Fiscal only (faster)
python scripts/generate_policy_impacts.py --skip-household
```

### 3. Documentation (Jupyter Book)
*   **Build:** `cd jupyterbook && myst build --html`
*   **Preview:** `cd jupyterbook && myst start`
*   **Important:** Notebooks (`.ipynb`) must be executed and have outputs *before* committing. The CI checks for this.
    *   Command: `jupyter nbconvert --to notebook --execute --inplace *.ipynb`

### 4. Dashboard (React)
*   **Run Dev:** `cd policy-impact-dashboard && npm start`
*   **Build:** `cd policy-impact-dashboard && npm run build`
*   **Data Source:** Loads `public/policy_impacts.csv` (copied from `data/` during build/setup).

## Critical Rules & Gotchas

*   **Option 4 Credit Amount:** The "Social Security Tax Credit System" (Option 4) uses a **$500** credit. Do **NOT** change this to $900 or any other value unless explicitly instructed. This is hardcoded in `src/reforms.py`.
*   **Notebook Execution:** CI will fail if notebooks are committed without outputs. Always execute them before pushing.
*   **Deployment:** Documentation is deployed via GitHub Actions. Do not manually push to `docs/`.
*   **Vectorized Calculations:** Household impacts use vectorized operations. Avoid loops over households/people in Python; rely on PolicyEngine's array capabilities.

## Common Commands (Makefile)

*   `make all`: Install deps, generate data, build book & dashboard.
*   `make data`: Generate all impact data.
*   `make book`: Build the Jupyter Book.
*   `make test`: Run Python and React tests.
*   `make lint`: Check formatting (Black, Pylint, ESLint).

# crfb-tob-impacts

Social Security taxation reform analysis with PolicyEngine.

## Quick Start

```bash
# Setup environment with uv and Python 3.13
uv venv --python 3.13
source .venv/bin/activate
uv pip install -e .

# Generate policy impact data (takes 15-30 minutes)
python scripts/generate_policy_impacts.py

# Build Jupyter Book documentation
cd jupyterbook && jupyter-book build .

# Run React dashboard
cd policy-impact-dashboard && npm install && npm start
```

## Project Structure

- `src/` - Core Python modules (reforms, calculations)
- `jupyterbook/` - Jupyter Book documentation
- `policy-impact-dashboard/` - React visualization dashboard
- `data/` - Generated CSV data files
- `tests/` - Test suite

## Data Generation

The project uses PolicyEngine to simulate fiscal and household impacts:

- **scripts/generate_policy_impacts.py** - Data generation using PolicyEngine simulations
- Output saved to `data/` and dashboard `public/` directories

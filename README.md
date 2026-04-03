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
cd jupyterbook && myst build --html

# Run Next dashboard
cd dashboard && npm ci && npm run dev
```

## Project Structure

- `src/` - Core Python modules (reforms, calculations)
- `jupyterbook/` - Jupyter Book documentation
- `dashboard/` - Next.js visualization dashboard
- `data/` - Generated CSV data files
- `tests/` - Test suite

## Deployment

The production site is deployed on Vercel as a combined static build:

- documentation at `/`
- dashboard at `/dashboard`

Local production-style build:

```bash
python3 -m pip install -e .
npm --prefix dashboard ci
./scripts/build_vercel_site.sh
```

That writes the combined output to `.vercel-site/`.

## Data Generation

The project uses PolicyEngine to simulate fiscal and household impacts:

- **scripts/generate_policy_impacts.py** - Data generation using PolicyEngine simulations
- Output saved to `data/` and dashboard `public/` directories
- **PolicyEngine-US Version**: 1.398.0

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

# Run Next dashboard
cd dashboard && bun install && bun run dev
```

## Project Structure

- `src/` - Core Python modules (reforms, calculations)
- `dashboard/` - Next.js current-results dashboard
- `paper/` - Quarto manuscript for citation and formal review
- `data/` - Generated CSV data files
- `tests/` - Test suite

## Deployment

The production site is deployed on Vercel as a combined static build:

- dashboard at `/`
- citable Quarto paper at `/paper/`

When `NEXT_PUBLIC_BASE_PATH` is set, both the dashboard and paper are emitted
under that base path.

Local production-style build:

```bash
python3 -m pip install -e .
cd dashboard && bun install && cd ..
./scripts/build_vercel_site.sh
```

That writes the combined output to `.vercel-site/`.

## Data Generation

The project uses PolicyEngine to simulate fiscal and household impacts:

- **scripts/generate_policy_impacts.py** - Data generation using PolicyEngine simulations
- Output saved to `data/` and dashboard `public/` directories
- **PolicyEngine-US Version**: 1.398.0

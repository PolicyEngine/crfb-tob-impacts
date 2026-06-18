# crfb-tob-impacts

Social Security taxation reform analysis with PolicyEngine.

## Reform Modeling Stop Sign

Before any paid CRFB reform Modal launch, read
[`REFORM_MODELING_BIBLE.md`](REFORM_MODELING_BIBLE.md). It points to the
controlling command-center plan and progress ledger. The required production
artifact is a full reform output H5 in durable storage for each `(year, reform)`
cell.

## Quick Start

The quick-start commands below are legacy local-development guidance. They are
not the CRFB reform-modeling relaunch path and must not be used to launch paid
Modal reform work. For reform modeling, use
[`REFORM_MODELING_BIBLE.md`](REFORM_MODELING_BIBLE.md).

```bash
# Setup environment with uv and Python 3.13
uv venv --python 3.13
source .venv/bin/activate
uv pip install -e .

# Build reform data on Modal, then assemble locally (see `make data`)
make panel
python scripts/assemble_reform_panel.py
python scripts/build_dashboard_results.py

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

The legacy local project uses PolicyEngine to simulate fiscal and household
impacts:

- **scripts/generate_policy_impacts.py** - Data generation using PolicyEngine simulations
- Output saved to `data/` and dashboard `public/` directories
- Historical pinned examples may cite older PolicyEngine-US versions. Do not
  treat those examples as the active reform relaunch contract.

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

## Canonical Reform Pipeline

The active CRFB reform-modeling path is `modal_batch/run_panel.py`, with
separate local assembly scripts. These constraints are part of the production
contract:

- Static scoring covers the full selected-cells panel: annual 2026-2035, every
  five years from 2040-2100, and the option12 transition junctures.
- Behavioral scoring is endpoint-only: compute 2026 and 2100, then let
  `scripts/assemble_reform_panel.py` interpolate each reform's behavioral/static
  multiplier across display years. Do not fan labor-supply-response scoring out
  per year.
- OASDI/HI decomposition is an endpoint pass that reuses
  `materialize_tob_revenue_pair`; do not duplicate trust-fund split formulas.
- Long Modal baseline/scoring cells are nonpreemptible, because preemption lost
  prior far-horizon work before it could commit.
- `results/reform_panel.json` is assembled by
  `scripts/assemble_reform_panel.py`; `modal_batch/run_panel.py` writes only the
  raw orchestrator dump at `results/run_panel_raw.json`.

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

Generated dashboard and paper data should come from the canonical reform
pipeline above. Historical local scripts and pinned examples may cite older
PolicyEngine-US versions; do not treat those examples as the active reform
relaunch contract.

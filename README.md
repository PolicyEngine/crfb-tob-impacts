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

# Aggregate previously approved full-H5 artifacts, then rebuild dashboard data
python scripts/aggregate_reform_full_h5_results.py
python scripts/build_dashboard_results.py

# Run Next dashboard
cd dashboard && bun install && bun run dev
```

## Canonical Reform Pipeline

The active CRFB reform-modeling path is
`modal_batch/reform_full_h5.py::submit_reform_full_h5`. Every paid production
cell must persist a full reform-output H5 plus metadata before any aggregate
table is accepted. These constraints are part of the production contract:

- Static scoring covers the full selected-cells panel: annual 2026-2035, every
  five years from 2040-2100, and the option12 transition junctures.
- Behavioral scoring is endpoint-only: compute 2026 and 2100, then publish
  annual behavioral rows by interpolating each reform's behavioral/static
  multiplier across display years. Do not fan labor-supply-response scoring out
  per year.
- OASDI/HI decomposition reads the engine's `tob_revenue_oasdi` and
  `tob_revenue_medicare_hi` exactly as computed; do not floor, cap or
  re-derive the trust-fund split in this repo.
- Long Modal baseline/scoring cells are nonpreemptible, because preemption lost
  prior far-horizon work before it could commit.
- The public result surface is `results.csv` plus
  `dashboard/public/data/results.csv`; those CSVs are derived from the durable
  full-H5 cells, not treated as source artifacts.

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

For local projected-year builds, `scripts/build_projected_datasets.py` accepts
`--economic-assumption-reform MODULE:ATTRIBUTE`. This hook is off by default.
When enabled, Stage A requires an entity-level single-year base and extends it
with the reformed system's per-capita uprating series, through the requested
year or `STAGE_A_STORED_END_YEAR`, whichever comes first. Each stored year holds
a copy of the inputs it changes, so storing every year through 2100 would not
fit in memory on the full base. Past the stored years, Core uprates each input
from its last stored year with the simulation's own parameters, so the inputs
and the income-growth caps stay on the same economic path. A test compares this
path with a fully stored one on the real engine. A base that already contains
multiple years is refused because its later inputs may carry a different aging
path. Builds without the hook stop entity-level input extension at the same
year.

The year frame keeps the base file's `person_id` in every year. Its formula
numbers rows past the stored years, and claim-age draws key on it. Group IDs
have no formula and carry forward unchanged.

The build applies the economic assumption before the tax assumption in every
simulation. Each year file embeds the economic record in its H5 and repeats
it in the metadata sidecar, including whether inputs aged under that assumption
and the extension's end year. Scorers apply the same recorded economic and tax
assumptions to the baseline and policy simulations. They refuse disagreeing
records or an H5 that names an economic assumption whose sidecar is missing.

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
- **PolicyEngine-US Version**: 1.398.0

## Saved-H5 Rescoring

For long-run checks, this repo can rescore reforms against prebuilt H5 datasets
instead of the legacy baseline-override CSV workflow.

Use [scripts/score_saved_h5_reforms.py](/Users/maxghenis/PolicyEngine/crfb-tob-impacts/scripts/score_saved_h5_reforms.py):

```bash
export CRFB_TAX_ASSUMPTION_MODULE=/absolute/path/to/policyengine-us-data/policyengine_us_data/datasets/cps/long_term/tax_assumptions.py

PYTHONPATH=/absolute/path/to/policyengine-us \
uv run python scripts/score_saved_h5_reforms.py \
  --dataset oact2100=/absolute/path/to/2100.h5 \
  --reform option1 \
  --reform option8 \
  --reform option11 \
  --tax-assumption-module "$CRFB_TAX_ASSUMPTION_MODULE" \
  --compare-csv results/oact_static_current.csv \
  --compare-units billions \
  --output results/local_oact_saved_h5_checks.csv
```

Notes:
- The current long-run checks depend on the local `policyengine-us` wage-base fix from PR `#7912`.
- The scorer validates saved-H5 metadata against the expected calibration profile, target source, and tax-assumption name before running.
- The scorer forces saved-H5 metadata validation even if `CRFB_ALLOW_UNVALIDATED_DATASETS=1` is set in the shell.
- The scorer also rejects filename/metadata year mismatches, so mislabeled H5 files do not get scored for the wrong period.
- If `--tax-assumption-module` is omitted, the scorer tries common local checkout paths or `CRFB_TAX_ASSUMPTION_MODULE`.
- Legacy CRFB results CSVs are in billions, while saved-H5 rescoring outputs are in dollars.
- `results/oact_static_current.csv` is treated as a frozen legacy comparison artifact. The post-OBBBA baseline scripts do not overwrite it.
- Baseline summaries are cached under `.cache/saved_h5_baselines/` so repeated checks on the same year can skip the initial baseline pass.
- A tracked summary of the representative deltas lives in [analysis/saved_h5_representative_checks.md](/Users/maxghenis/PolicyEngine/crfb-tob-impacts/analysis/saved_h5_representative_checks.md).
- The backing three-year local artifacts used for those tables are `results/local_oact_saved_h5_3year_checks.csv` and `results/local_oact_saved_h5_3year_checks_billions.csv`. Those are local runtime outputs, not tracked repo artifacts.
- Completed `2090`/`2100` all-reforms summaries live in [analysis/saved_h5_all_reforms_2090_2100.md](/Users/maxghenis/PolicyEngine/crfb-tob-impacts/analysis/saved_h5_all_reforms_2090_2100.md).
- A broader tracked findings note lives in [analysis/long_run_rescoring_findings.md](/Users/maxghenis/PolicyEngine/crfb-tob-impacts/analysis/long_run_rescoring_findings.md).

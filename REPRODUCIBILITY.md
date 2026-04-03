# Reproducibility Notes

This repository's historical 75-year results were not produced from a fully pinned,
single-repo workflow. The model and data dependencies lived in sibling repos and
the batch scripts assumed unpublished Hugging Face dataset paths.

This file records the exact PRs and SHAs that matter and the environment variables
needed to rerun the analysis from local checkouts.

## What mattered historically

### `policyengine-us-data` (Baogorek)

These are the relevant data-side PRs:

- `PolicyEngine/policyengine-us-data#443`
  - Branch: `long-term`
  - Merge SHA: `e2137590948d21d07423b6919a55ee513e0e3159`
  - Added the 75-year long-term projection pipeline.
- `PolicyEngine/policyengine-us-data#448`
  - Branch: `documentation-nov`
  - Merge SHA: `ed6a0b48e33ac5c5a740f31b26a77c1f359f6a76`
  - Added H6 calibration support.
- `PolicyEngine/policyengine-us-data#460`
  - Branch: `tob-calibrate`
  - Head SHA: `be4027f3f18031ca7a7212aaf50f1c671b23ef06`
  - Merge SHA: `9649e4b053daeeb2eba9e4dfbc72a20181423a36`
  - Added TOB calibration targets for `tob_revenue_oasdi` and `tob_revenue_medicare_hi`.
- `PolicyEngine/policyengine-us-data#505`
  - Branch: `fix-stale-calibration-targets-503`
  - Merge SHA: `79c36cda160569ec7319bc71386ebfc0cbba9281`
  - Fixed stale 2022-2023 calibration targets being applied to a 2024 dataset.

Important timing note:

- `crfb-tob-impacts` switched to `no-h6` datasets in commit `dedecaa08e90517875f4a4085f869aace3c308d7` on December 19, 2025.
- `policyengine-us-data#460` merged on December 23, 2025.
- That means the historical run likely used Baogorek's `tob-calibrate` branch directly or an equivalent local checkout, not just upstream `main` as of December 19, 2025.

### `policyengine-us`

I did not find a matching Baogorek-authored TOB PR in `policyengine-us`.
The model-side branches that matter are:

- `PolicyEngine/policyengine-us#6750`
  - Branch: `add/tob-revenue-variables`
  - Merge SHA: `38b115860dde5640e0e750bd7c7cf5a619e99b0f`
  - Added `tob_revenue_total`, `tob_revenue_oasdi`, and `tob_revenue_medicare_hi`.
- `PolicyEngine/policyengine-us#6830`
  - Branch: `add-labor-supply-elasticity-age-heterogeneity`
  - Head SHA: `1902f30eef1a9c2f3c8e3e6b3b486f97e8063cca`
  - This PR was never merged upstream. The old batch guide shows it was merged locally on top of `#6750` for dynamic runs.
- `PolicyEngine/policyengine-us#6999`
  - Branch: `ss_tob_fix`
  - Merge SHA: `29e11d0a2178493c70a15c816f809efeeb38e6ad`
  - Fixed the OASDI/HI TOB split from a tier-proportion approximation to a double-branching statutory allocation.

## Why this matters for result quality

- Without data-side TOB calibration, the mismatch was large. In `policyengine-us-data#460`, Baogorek documented a 2025 baseline miss of:
  - OASDI TOB: `$18.5B` modeled vs `$60.5B` target (`-69%`)
  - HI TOB: `$73.1B` modeled vs `$40.7B` target (`+80%`)
- Without `policyengine-us-data#505`, the data pipeline could also calibrate to stale 2022-2023 targets while using a 2024 dataset.
- Without `policyengine-us#6999`, the model can still be internally "consistent" with calibrated baseline targets, but it is using the wrong definition for how reform-induced TOB changes split between OASDI and HI.

## Reproducible rerun path

The batch code now supports two environment variables:

- `CRFB_POLICYENGINE_US_PATH`
  - Path to a local `policyengine-us` checkout to import or bundle.
- `CRFB_DATASET_TEMPLATE`
  - Dataset template, for example:
  - `/absolute/path/to/projected_datasets/{year}.h5`

### Recommended current rerun

Use a current local `policyengine-us` checkout that contains `#6999`, and a current
`policyengine-us-data` checkout that contains `#505`.

Example local dataset build from `policyengine-us-data`:

```bash
cd /Users/maxghenis/PolicyEngine/policyengine-us-data
uv run --extra calibration python policyengine_us_data/datasets/cps/long_term/run_household_projection.py \
  2026 2026 --greg --use-ss --use-payroll --use-tob --save-h5
```

Point this repo at the generated datasets:

```bash
export CRFB_POLICYENGINE_US_PATH=/Users/maxghenis/PolicyEngine/policyengine-us
export CRFB_DATASET_TEMPLATE=/Users/maxghenis/PolicyEngine/policyengine-us-data/projected_datasets/{year}.h5
```

### Historical dynamic rerun

If the goal is to recreate the old dynamic stack as closely as possible, use a
separate worktree for `policyengine-us` and locally merge the unmerged draft PR:

```bash
git -C /Users/maxghenis/PolicyEngine/policyengine-us fetch upstream
git -C /Users/maxghenis/PolicyEngine/policyengine-us worktree add /tmp/policyengine-us-crfb 38b115860dde5640e0e750bd7c7cf5a619e99b0f
git -C /tmp/policyengine-us-crfb merge --no-edit 1902f30eef1a9c2f3c8e3e6b3b486f97e8063cca
export CRFB_POLICYENGINE_US_PATH=/tmp/policyengine-us-crfb
```

For the data side, the historical run most likely depended on Baogorek's
`tob-calibrate` branch state around PR `#460`.

## March 27, 2026 smoke test

From `/Users/maxghenis/PolicyEngine/policyengine-us-data`, this command succeeded:

```bash
uv run --extra calibration python policyengine_us_data/datasets/cps/long_term/run_household_projection.py \
  2026 2026 --greg --use-ss --use-payroll --use-tob --save-h5
```

Observed output for 2026:

- Baseline before calibration:
  - SS: `$1541.8B` vs target `$1701.3B`
  - Payroll: `$9511.0B` vs target `$11129.0B`
  - OASDI TOB: `$60.2B` vs target `$76.8B`
  - HI TOB: `$39.2B` vs target `$52.2B`
- After calibration:
  - SS achieved exactly `$1701.3B`
  - Payroll achieved exactly `$11129.0B`
  - OASDI TOB achieved exactly `$76.8B`
  - HI TOB achieved exactly `$52.2B`
- Output dataset created successfully:
  - `/Users/maxghenis/PolicyEngine/policyengine-us-data/projected_datasets/2026.h5`

The generated dataset also loaded successfully through `policyengine-us`, and
returned:

- `default_period=2026`
- `tob_revenue_oasdi=76.8`
- `tob_revenue_medicare_hi=52.2`
- `income_tax=3515.5`

So the data-side rerun path is reproducible locally. The remaining gap in this
repo was the hard-coded dependency on unpublished `hf://policyengine/test/no-h6/{year}.h5`
paths, which is now overrideable.

## Direct post-OBBBA dashboard fix

For the narrow CRFB dashboard issue Mark Sarney raised on March 26, 2026, this
repo now vendors an explicit TOB baseline table at:

- `data/ssa_tob_baseline_75year.csv`

That file carries the annual OASDI and HI TOB baseline totals used for the
baseline-share allocation logic. To stamp those values into the shipped CSVs and
regenerate the combined export, run:

```bash
cd /Users/maxghenis/PolicyEngine/crfb-tob-impacts
python3 scripts/apply_post_obbba_tob_baseline.py
```

This updates both:

- the repo-level `all_static_results.csv` / `all_dynamic_results.csv`
- the published dashboard copies under `dashboard/public/data/`

and then rebuilds `dashboard_data_combined.csv`.

It does not update `results/oact_static_current.csv`; that file remains the
legacy published-output comparison point for the saved-H5 rescoring checks.

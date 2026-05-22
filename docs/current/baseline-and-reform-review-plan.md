# Baseline and Reform Review Plan

This plan governs CRFB long-run baseline datasets and static reform results.
Its purpose is to catch invalid baseline facts before reform compute starts and
to review reform results as they arrive, not only at release packaging time.

## Current Reproducibility Contract

The current production baseline does not depend on a published `policyengine.py`
bundle. It is reproducible through the explicit dataset, source, runtime, and
artifact pins below.

### Baseline Run

- Run ID: `crfb-longrun-20260520-5a35713-annual`.
- Modal volume: `policyengine-us-data-long-term`.
- Modal volume prefix: `/crfb-longrun-20260520-5a35713-annual`.
- Production manifest: `long_run_production_manifest.json`.
- Data source repository: `PolicyEngine/policyengine-us-data`.
- Source SHA: `5a357137e2fd33975745603915e98a51b7be81d0`.
- Base dataset:
  `hf://policyengine/policyengine-us-data/enhanced_cps_2024.h5@688f972425f5e858fc52bda2b696e0af74fea920`.
- Package versions:
  - `policyengine-core==3.26.1`
  - `policyengine-us==1.700.2`
  - `policyengine-us-data==1.115.5`
- `policyengine-us` package tree SHA256:
  `e3b3e42002892f1c9ae576a3b96aeeda55b0f504cfc8623adbb9e06cce441f18`.
- Projection command: recorded in the production manifest.
- Projection years: annual `2026-2100`.
- Projection profile: `ss-payroll-tob`.
- Target source: `trustees_2025_current_law`.
- Target source SHA256:
  `e059aa9fba806b260a399b8a6a18b892a6363ba12ee00fe21ab109d09dff0ec4`.
- Tax assumption: `trustees-2025-core-thresholds-v1`.
- Support augmentation profile: `donor-backed-composite-v1`.
- Support augmentation parameters:
  - start year `2075`
  - target year `2100`
  - top targets `60`
  - donors per target `10`
  - max distance `5.0`
  - clone weight scale `0.1`
  - blueprint base weight scale `5.0`
  - sanitize clone non-target income `true`
  - sanitize worker non-target income `false`
  - align to run year `false`

Each baseline H5 must be accompanied by its `YYYY.h5.metadata.json`, and the
metadata must match this run ID, source SHA, base dataset URI, package tree
SHA256, target source, tax assumption, and support augmentation settings where
applicable.

### Reform Runs

Reform workers are reproducible only when the submission manifest and recovered
artifacts identify the exact cell and preserve the raw scenario output.

For every reform batch, record:

- Submission JSON path.
- Modal app ID or name.
- Modal function call IDs.
- Modal volume prefix.
- Years and reform IDs.
- `use_baseline_artifacts` setting.
- Calibration-quality gate settings.
- Whether raw reform H5 persistence was enabled.
- Local recovered output directory.
- Merged output CSV path.

For every future reform cell, require:

- Cell CSV row.
- `reform_raw_h5_saved == True`.
- Raw H5 artifact:
  `reform_raw_h5/year=YYYY/reform=OPTION/scenario.h5`.
- Raw H5 metadata:
  `reform_raw_h5/year=YYYY/reform=OPTION/metadata.json`.
- Raw H5 size, entity count, variable count, and artifact type recorded in the
  cell CSV.
- Object-store mirror location when configured.

Older completed rows without raw H5 artifacts may be used only as aggregate
results after MicroSeries/MicroDF validation. They are not considered fully
durable for future reaggregation unless rerun or otherwise recovered with raw
scenario H5s.

### Current Reform Artifact Status

- Current public result surface:
  `results.csv` and `dashboard/public/data/results.csv`.
- Current release result archive:
  `results/results_full_h5_selected_panel_display_20260522.csv`.
- Static and labor-supply response source CSVs exist only as build inputs to the
  unified `results.csv`; consumers should filter `scoring_type` instead of
  choosing a source file.
- Raw full-H5 reform artifacts are required for future reform reruns and
  reaggregation; stale patch and sparse-tail CSVs are not part of the current
  delivery surface.

Before launching any new reform batch, verify that the batch will use baseline
artifacts from `crfb-longrun-20260520-5a35713-annual`, enforce the
`policyengine-us` package tree SHA256 contract, and save raw reform H5 artifacts.

## Aggregation Rule

Never aggregate PolicyEngine results by manually multiplying values by
household weights. Aggregates must come from PolicyEngine/MicroDF weighted
operations, such as `MicroSeries.sum()`.

Raw microdata and per-household diagnostic arrays may be saved for audit and
reaggregation, but any reaggregation from those saved artifacts must first
reconstruct a weighted MicroDF/MicroSeries-style object and then use normal
weighted operations. Direct `np.dot(values, household_weight)` is not allowed
for fiscal or dashboard results.

## Baseline Dataset Review

Run this review immediately when a new baseline year dataset completes and
before submitting reforms for that year.

### Required Artifacts

- H5 dataset for the year.
- Metadata JSON for the H5.
- Baseline aggregate/preflight row produced with MicroSeries aggregation.
- Calibration diagnostics from dataset metadata.
- Dashboard baseline facts row or preflight plot input row.

### Provenance Checks

- H5 path, metadata path, file size, and hashes match the manifest.
- Metadata year equals the target year.
- Source SHA, PolicyEngine US version, calibration profile, target source, and
  tax assumption match the run manifest.
- No stale baseline metrics artifact is used for aggregate totals.

### Aggregate Checks

For the completed year, record and inspect:

- GDP.
- Federal income tax.
- Federal income tax as percent of GDP.
- OASDI taxable payroll.
- HI taxable payroll.
- Social Security benefits.
- OASDI TOB, HI TOB, and total TOB.
- TOB as percent of payroll.

Compare each aggregate against:

- The prior accepted CRFB run.
- Adjacent completed years.
- Trustees/CRFB target rows where applicable.

### Microdata Sentinels

For all years, and especially 2075 onward, inspect weighted totals and
distribution tails for:

- `employment_income_before_lsr`
- `self_employment_income`
- `sstb_self_employment_income_before_lsr`
- `partnership_s_corp_income`
- `farm_operations_income`
- `taxable_private_pension_income`
- `taxable_ira_distributions`
- `taxable_401k_distributions`
- `qualified_dividend_income`
- `taxable_interest_income`
- `long_term_capital_gains`

Late-year review must include top-contributor diagnostics, not only totals.
At minimum: weighted total, p50, p99, p99.9, top 10 contributor share, and
largest record contribution.

### Baseline Decision

- `green`: provenance matches, fiscal ratios are plausible, calibration is
  valid, and sentinel distributions are coherent. Reforms may start.
- `yellow`: results are usable only after a written note explaining the
  anomaly and why it is not material.
- `red`: do not submit reforms for the year.

## Reform Result Review

Run this review as soon as a reform year completes, before merging that year
into the selected panel.

### Completion Checks

- All requested standard options are present exactly once.
- Baseline columns are identical across options in the same year.
- Scenario/metric artifacts exist where configured.
- Call IDs, dataset path, source SHA, and scoring mode are recorded.

### Fiscal Checks

For each option, inspect:

- Revenue impact in dollars.
- Revenue impact as percent of GDP.
- Revenue impact as percent of taxable payroll.
- Reform revenue relative to baseline revenue.
- TOB impacts by OASDI and HI.

Compare against:

- Prior accepted run for the same year and option.
- Adjacent completed years for the same option.
- The expected policy shape for the option.

### Shape Checks

- Repeal-style options should have the expected sign.
- Payroll-rate options should scale with taxable payroll.
- Cap/base options should not have unexplained discontinuities.
- 2075+ five-year intervals must be smooth unless policy thresholds or
  demographic changes explain the movement.

### Microdata Checks

For saved reform microdata/metric artifacts:

- Reaggregate any needed totals only through MicroDF/MicroSeries operations.
- Identify top contributors to revenue and TOB changes.
- Confirm impacts are not driven by a small number of implausible business
  income records.
- For 2075+, inspect whether `partnership_s_corp_income`,
  `self_employment_income`, or SSTB variables explain any large movement.

### Reform Decision

- `accept`: year can enter the merged selected panel.
- `hold`: keep artifacts but exclude from dashboard/release until reviewed.
- `reject`: do not use; document blocker, dataset, option, year, and call ID.

## Dashboard Timing

The dashboard baseline facts input must be built from the baseline preflight
artifact before reforms are submitted. The same facts should be plotted for
visual review:

- Federal income tax / GDP.
- TOB / payroll.
- Social Security and taxable payroll levels.
- Late-year business-income sentinel totals and tail concentration.

Reform dashboard rows should remain provisional until their reform review
summary is `accept`.

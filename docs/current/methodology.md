# Current Methodology

This page describes the live modeling contract for the current CRFB rerun.

## Scope

The active package contains the standard reforms `option1` through `option12`.
Legacy non-contract variants are not part of the current dashboard, release, or
reform-modeling contract.

The package also defines `reverse_roth` as a new proposal scenario: immediately
tax 100% of Social Security benefits and make employee OASDI payroll taxes
deductible from income tax. It is runnable as an explicit reform ID, but it is
not part of the current published `option1` through `option12` result set until
full reform H5 cells are produced, stored, and aggregated under the production
contract.

The main delivery window is `2026-2100`.

## Standard Series Contract

For the current v2/populace rerun, the release contract is:

- target source: 2026 Trustees Reports, intermediate assumptions, with OBBBA in
  current law
- baseline run ID: `crfb-longrun-v2pop-tr2026-noclone-9f1260b-20260612`
- populace base: `populace-us-2024-9f1260b-20260611`
- exact H5 anchors: `2026`, `2030`, and every fifth year from `2035` through
  `2100`
- reforms: `option1` through `option12`, `reverse_roth`, and `tax93`
- static exact rows: saved full reform H5 artifacts in R2 under
  `v2pop_tr2026_20260611` and `v2pop_tr2026_noclone_20260612`
- behavioral rows: exact full-H5 endpoints in `2026` and `2100`, with annual
  non-endpoint rows produced by the documented endpoint-ratio interpolation

The named threshold assumption remains
`trustees-2025-core-thresholds-v1` because that is the actual PolicyEngine
tax-threshold reform used by the H5s. It is a tax-indexing assumption name, not
the data-target vintage. The data targets and release lineage are TR2026.

## Trustees Tax-Threshold Assumption

The named tax assumption `trustees-2025-core-thresholds-v1` operationalizes the
Trustees/OACT long-run taxation-of-benefits assumption for microsimulation.
SSA/OACT clarified by email to PolicyEngine on May 5, 2026 that the long-range
assumption applies both to income-tax rate brackets and to federal income-tax
thresholds such as standard deductions.

Operationally, this means:

- Social Security benefit-tax combined-income thresholds remain fixed in nominal
  dollars.
- Federal income-tax rate brackets and related federal income-tax thresholds
  follow current-law C-CPI-U indexing for the first ten projection years, through
  `2034`.
- Beginning in `2035`, those federal income-tax brackets and thresholds rise
  with average wages.

The implemented core-threshold bundle covers ordinary income-tax brackets,
standard deductions, aged/blind standard deduction additions, capital-gains
thresholds, and AMT thresholds. This is a Trustees-lineage scoring assumption
for the CRFB long-run TOB work, not default statutory current law.

## Late-Year Support

The v2/populace construction does not use synthetic household support in
the published years. Demographics are carried through household weights; broad
economic growth is carried through input values before a final light calibration
to TR2026 benefits, taxable payroll, and TOB targets. Late-year support gates
still apply and are documented in
[late-year-support-gates.md](late-year-support-gates.md), but the current
published H5s pass those gates without synthetic household support.

## Scenario Families

### Standard options `1-12`

These are scored by rescoring reforms against validated yearly H5 datasets.

The important methodological point is that the current standard series is meant
to come from exact yearly microdata plus direct reform rescoring, not from
patching the old stitched CSVs in place.

## Static Versus Supplemental Labor-Supply Response

The released static series uses the cleaned Trustees baseline lineage and is
the primary CRFB dashboard scoring surface. The supplemental labor-supply
response series shares the same baseline levels before being published
alongside the static release.

For the labor-supply response release, the intended differences from plain upstream
`policyengine-us` main are:

- Trustees long-run uprating behavior
- age-based labor-supply elasticities for behavioral-response scoring

Labor-supply response scoring should therefore be interpreted as a
partial-equilibrium estimate under PolicyEngine's elasticity assumptions, not
as a separate legacy workflow or as an exact replica of JCT/CBO conventional
practice.

Operationally:

- the publication-facing dashboard defaults to static scoring and includes
  supplemental behavioral rows generated from the current full reform-H5
  endpoint contract
- any labor-supply response release must start from durable
  `reform_full_h5/year=YYYY/reform=optionX/scenario.h5` artifacts; aggregate
  CSVs and non-contract sample panels are not production inputs

## Reproducibility Boundary

The repo-level standard now is:

- calibrated H5 snapshots with machine-readable metadata under
  `projected_datasets_v2pop/`
- baseline manifests under `docs/current/manifests/`
- the public `dashboard/public/data/results_contract.json`, which maps each
  published result row to baseline H5 hashes, reform run prefixes, scenario H5
  hashes where exact, and TR2026 targets
- source and output SHA-256 checksums in release packages built by
  `scripts/build_release_package.py`

## Interpretation Rules

- Current dashboard outputs should reflect only the current rerun results.
- Prior or legacy values belong only in comparison spreadsheets.
- The deleted legacy Jupyter Book is historical context, not the live
  methodology spec.
  [analysis/long_run_rescoring_findings.md](../../analysis/long_run_rescoring_findings.md).

## What Still Lives Elsewhere

- pinned dependency and environment notes:
  [REPRODUCIBILITY.md](../../REPRODUCIBILITY.md)
- audit trail and validation evidence:
  [analysis/long_run_rescoring_findings.md](../../analysis/long_run_rescoring_findings.md)

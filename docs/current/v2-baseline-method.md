# V2 baseline method: demographics in weights, economics in values

This documents the v2 long-horizon baseline construction introduced in June
2026, replacing the v1 `ss-payroll-tob` datasets
(`crfb-longrun-20260520-5a35713-annual`) for the every-fifth-year reform
panel.

## Why change

The v1 datasets hit their calibration targets exactly, but the division of
labor between weights and values created three structural problems:

1. **Aggregate-growth uprating double-counts population growth.** Several
   income uprating series in `policyengine-us` (for example
   `calibration.gov.irs.soi.social_security`, growing 5.33% per year after
   2035) are *aggregate* series, but uprating applies them to every record's
   *values* while household weights separately carry population growth. By
   2100 the raw simulation overshoots Trustees OASDI cost by roughly 45%,
   and the calibration must fix a value-level error with weights.
2. **Weight tilting concentrated the taxation-of-benefits base.** Forcing
   value-level gaps closed through weights pushed taxation-of-benefits
   contributor effective sample sizes to the low 20s and required
   donor-backed synthetic support from 2075 onward to stay feasible.
3. **Pre-OBBBA targets under post-OBBBA law.** The v1 datasets calibrated
   modeled TOB (under law that includes OBBBA) to the *pre-OBBBA* 2025
   Trustees current-law series, while the project's published baseline is
   the post-OBBBA series. The dashboard carried the resulting $16–27B gaps
   as `tob_*_gap_to_post_obbba_target` columns.

## The v2 construction

For each projection year Y, `scripts/build_v2_projected_datasets.py`:

- **Stage A — materialize.** Simulate the latest published enhanced CPS at
  year Y in a fresh simulation and export every true input variable at its
  year-Y (uprated) value. Derived variables are never stored, so formulas
  (including labor-supply responses) always recompute downstream.
- **Stage B — demographic reweight (light).** Entropy-balance household
  weights to the SSA Trustees age distribution (five-year buckets, exact),
  starting from the year-uprated base weights. This carries population
  level and age shape — the only job weights should do.
- **Stage C — value rescaling to Trustees aggregates.**
  - `alpha` rescales earnings inputs so SSA taxable payroll (wages capped
    at the wage base plus taxable self-employment income in remaining cap
    room) equals the Trustees taxable-payroll target.
  - `beta` rescales Social Security benefit inputs so total benefits equal
    Trustees OASDI cost. `beta` falls with horizon (about −1.9% per year),
    exactly offsetting the beneficiary-growth component embedded in the
    aggregate uprating series.
  - `gamma` rescales beneficiary households' non-earnings, non-benefit
    income (pensions, IRA distributions, interest, dividends, capital
    gains, rents) so modeled total taxation of benefits reaches the
    post-OBBBA target. This closes the TOB gap with values rather than
    weight tilts.
- **Stage D — final light calibration.** Entropy-balance from the Stage B
  weights to hit all five target families exactly: age distribution,
  Social Security benefits, taxable payroll, OASDI TOB, and HI TOB — the
  TOB targets now being the **post-OBBBA** series
  (`data/ssa_tob_baseline_75year.csv`). Because values already carry the
  economics, this pass needs only a small tilt.

Validation is artifact-true: target vectors for Stage D come from a
simulation over the written H5 (with the
`trustees-2025-core-thresholds-v1` assumption active from 2035), and final
weights are written back in place. Publication gates from
`docs/current/late-year-support-gates.md` are enforced at build time
(aggregate gates every year, contributor gates from 2075).

## Targets and sources

| Target | Source file | Notes |
| --- | --- | --- |
| Population by single year of age | `data/SSPopJul_TR2024.csv` | TR2024 vintage, same as v1; TR2025 single-year ages are not published in machine-readable form |
| OASDI benefits, taxable payroll | `data/social_security_aux_tr2025.csv` | 2025 Trustees Report |
| OASDI + HI taxation of benefits | `data/ssa_tob_baseline_75year.csv` | Post-OBBBA baseline (OACT Aug 5, 2025 deltas; HI bridged by matching the OASDI percentage change) |

## Differences from v1, by design

- **No donor-backed synthetic support.** With values at year-Y scale, the
  TOB-contributing population is broad enough that late years calibrate
  exactly on real records alone.
- **Post-OBBBA TOB baseline is the calibration target**, so dataset TOB
  equals the published baseline and the post-OBBBA gap columns vanish.
- **Demographics stay light.** Stage D tilts from the demographic solution
  by small ratios (about 1.3 at 2026) instead of three orders of magnitude.

## Known limitations

- The age-distribution file is TR2024-vintage (as in v1); SSA blocks
  automated retrieval of the TR2025 single-year population file.
- The enhanced CPS household-weight level (~170M households after age
  calibration) exceeds administrative household counts, and modeled
  aggregate income tax exceeds administrative collections. Both are
  upstream enhanced-CPS properties; v2 narrows the income-tax gap
  (roughly $8.9T vs $14.1T modeled for 2026 in v1) but does not close it.
  Reform impacts are computed as within-model differences, which removes
  the common level.
- `gamma` is a uniform scale on beneficiary households' other income; it
  matches the TOB level but not necessarily its distribution across the
  income spectrum.
- Sex and marital-status distributions are not yet calibration targets,
  although the Trustees population file provides them; they are candidate
  additions if TOB-by-filing-status composition needs tightening.

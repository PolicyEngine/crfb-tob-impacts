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
    gains, rents) toward the Trustees taxation-of-benefits target,
    best-effort: at far horizons the 85% inclusion cap saturates and TOB
    becomes nearly inelastic to other income, so `gamma` is bounded and
    the final calibration closes the remainder.
- **No synthetic support stage.** Earlier drafts appended jittered
  clones of real contributor households at far horizons; the populace
  base made that unnecessary and the machinery is removed (see git
  history for the implementation). The validation that justified
  removal: a clone-free build of 2100 — the hardest year, with the most
  extreme age shift — passes every publication gate with margin
  (taxation-of-benefits contributor effective sample sizes of 152 OASDI
  and 127 HI against the >=50 gate; top-10 contribution 17–21% against
  the <=50% gate), and all six far-horizon years pass with contributor
  ESS 107–156. Every record in every published year is a real survey
  household.
- **Stage D — final light calibration.** Entropy-balance from the
  demographic weights to hit all target families exactly: age
  distribution, Social Security benefits, taxable payroll, and the
  TR2026 current-law OASDI and HI taxation-of-benefits series. From 2075
  the calibration also pins two self-referential income guards (ordinary
  non-payroll income and preferential investment income, as in v1) so
  weight tilts cannot inflate other income to reach the TOB target.
  Because values already carry the economics, the early-year pass needs
  only a small tilt; late years lean on the broad real contributor base
  the value scaling preserves.

Validation is artifact-true: target vectors for Stage D come from a
simulation over the written H5 (with the
`trustees-2025-core-thresholds-v1` assumption active from 2035), and final
weights are written back in place. Publication gates from
`docs/current/late-year-support-gates.md` are enforced at build time
(aggregate gates every year, contributor gates from 2075).

## Targets and sources

All targets come from the **2026 Trustees Reports** (released June 9,
2026), whose current-law baseline includes OBBBA — eliminating the TR2025
post-OBBBA bridge (OACT letter deltas and the provisional HI scaling)
that earlier drafts of this work carried.

| Target | Source file | Notes |
| --- | --- | --- |
| Population by single year of age | `data/SSPopJul_TR2026_interim.csv` | TR2026 V.A3 group totals (under 20 / 20-64 / 65+) applied to the TR2024 single-year shape; interim until SSA posts the TR2026 single-year file |
| OASDI cost, taxable payroll | `data/social_security_aux_tr2026.csv` | TR2026 IV.B1 cost rate x VI.G1 payroll, intermediate assumptions |
| OASDI taxation of benefits | `data/social_security_aux_tr2026.csv` | TR2026 IV.B2 percent of payroll x VI.G1 payroll |
| HI taxation of benefits | `data/social_security_aux_tr2026.csv` | CMS 2026 Medicare Trustees expanded tables, annual through 2100 |

## Differences from v1, by design

- **No synthetic records.** Values at year-Y scale keep the
  TOB-contributing population broad enough that the populace base passes
  every late-year gate bare; v1's donor-backed synthetic support is
  removed entirely.
- **TR2026 current-law TOB is the calibration target** (OBBBA included
  natively), so dataset TOB equals the published baseline and the
  post-OBBBA gap columns vanish.
- **Demographics stay light.** Stage D tilts from the demographic solution
  by small ratios (about 1.3 at 2026) instead of three orders of magnitude.

## Known limitations

- The single-year age *shape* within broad groups is TR2024-vintage;
  group levels are TR2026. SSA has not yet posted the TR2026
  single-year-age population file.
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

## Wage-path vintage

The model law's long-run wage indexing (`gov.ssa.nawi` and the payroll
cap inside policyengine-us 1.700.2) follows the TR2025 intermediate
path; TR2026's average wage index runs about 18% higher by 2100. The
value-scaling stages pin taxable payroll, benefits, and TOB to TR2026
aggregates regardless, so this affects only the within-model bracket
positions of individual records. Updating the packaged NAWI path to
TR2026 is a follow-up policyengine-us change.

# Execution spec: recompute the Balanced Fix solvency baseline on the new certified base

Self-contained task spec. Goal: answer CRFB (Marc Goldwein, 2026-06-18) — score the reform
options against the **solvency baseline** (SS otherwise brought into balance), with the
OASDI / Medicare-HI / general-fund split, on the **new certified base** the live dashboard
uses; restore the dropped balanced-fix dashboard surface.

Repo: /Users/maxghenis/PolicyEngine/crfb-tob-impacts, branch v2-baseline-method.

> This spec was hardened after an adversarial review (analysis note 2026-06-18). The review
> found three correctness BLOCKERS that would silently publish wrong numbers; the relevant
> fixes are inlined below and marked **[B1]/[B2]/[B3]**. Read the whole thing before running.

## Status of the no-compute pieces (already done — verify, do not redo)
- The current-law panel already exposes general-fund effects in the dashboard by
  deriving `revenue_impact - tob_oasdi_impact - tob_medicare_hi_impact` at read
  time from `results.csv`; there is **not** a persisted `general_fund_impact`
  column in the canonical CSV. VERIFIED 2026-06-18: existing columns reconcile
  to zero drift; Reverse Roth 2026 revenue -$46.81B = OASDI +$4.44B + HI
  +$53.37B + **general fund -$104.63B** (the above-the-line employee-OASDI
  payroll-tax deduction — this is the answer to Marc #3).
- For any new solvency-baseline output, either persist `general_fund_impact` in
  the new solvency file or document that the dashboard derives it the same way.
  In both cases, validate OASDI + HI + general fund = total to 1e-8.
- reverse_roth is answered by the current-law general-fund derivation ONLY. Do
  NOT score it against the solvent baseline (that would add a 5th, costlier
  reform for no ask).

## Reforms to score against the solvent baseline (exactly four)
Marc's words -> option ids: "Phased Roth" = **option12**, "repeal" = **option1**,
"85%" = **option2**, "100%" = **option8**.
- **Do NOT relabel reforms.py.** `dashboard/src/lib/reforms.ts` already maps option12 ->
  "Phased Roth" (shortName) and a pinned test (`tests/test_release_artifacts.py`
  test_dashboard_uses_crfb_roth_naming) guards those exact strings. Emit rows with the bare id
  (`reform_name="option12"`, matching the live CSV convention); reforms.ts supplies the label.
- option12's dict (src/reforms.py ~622-712) changes SS *taxability*, NOT payroll rates or
  benefit levels, so it does not collide with the balanced fix's rate/benefit changes — good.

## [B1] Build EVERY sim with the Trustees current-law reform stacked
The new certified base stores INPUT data only; the Trustees long-run tax assumption is applied
at calibration time, not baked into the H5. Both new-base scoring paths stack it explicitly:
`src.reform_full_h5_worker.materialize_tob_revenue_pair` uses
`current_law = _tax_assumption_reform(year)` (returns **None before 2035**;
`TAX_ASSUMPTION_START_YEAR = 2035` in src/pipeline.py).
- Historical option13 scripts built `Microsimulation(dataset=...)` with NO reform.
  **Do not copy that.** On the new base it yields literal current-law SS
  thresholds, not the Trustees wage-indexed path the base was calibrated against, so every gap,
  TOB, multiplier, and rate would be silently wrong while still "closing to ~0".
- REQUIRED: build the baseline as
  `dataset_microsimulation({year}.h5, reform=_tax_assumption_reform(year))`
  and stack everything else on top of that current-law reform.

## [B2] Gap-closing as a hand-built sim sequence (the benefit cut is a set_input)
The Stage-1 benefit cut is NOT a parameter reform. It is
`sim.set_input("social_security", year, reduced_values)` after construction.
The Stage-2 rate increase IS a parameter reform (OASDI + HI payroll rates).
So the solvent baseline = current-law reform + rate reform + set_input benefit
cut. The cut **cannot** be a tuple component; the spec's old
`income_tax((solvent, reform))` one-liner is wrong.

The exact mechanics are inlined here. Do not depend on any archived Option
13/14 runner; those entry points are fail-closed and not part of the current
pipeline.

1. `base = dataset_microsimulation({year}.h5, reform=_tax_assumption_reform(year))`.
2. From `base`, read `ss = base.calculate("social_security", year)` and compute the gaps
   (direct `.calculate(...).sum()` on `base` — these variables self-branch natively, so do NOT
   wrap them in materialize_tob_revenue_pair for the GAP math):
   - SS income = employee_social_security_tax + employer_social_security_tax
     + self_employment_social_security_tax + tob_revenue_oasdi
   - SS gap = SS income - ss_benefits
   - HI income = employee_medicare_tax + employer_medicare_tax
     + self_employment_medicare_tax + additional_medicare_tax
     + tob_revenue_medicare_hi
   - HI gap = HI income - medicare_expenditures
3. Derive the benefit cut ONCE per year:
   - `ss_benefits = ss.sum()`
   - `ss_values = np.asarray(ss.values)`
   - `ss_shortfall = abs(min(ss_gap, 0))`
   - `benefit_cut = ss_shortfall * 0.5`
   - `benefit_multiplier = 1 - benefit_cut / ss_benefits`
   - `reduced_ss = ss_values * benefit_multiplier`
4. Build a Stage-1 sim with the Trustees current-law reform and the benefit cut
   only. This is a separate heavy sim whose only purpose is to measure gaps after
   benefit cuts and TOB feedback:
   ```
   stage1 = dataset_microsimulation(
       {year}.h5,
       reform=_tax_assumption_reform(year),
       start_instant=f"{year}-01-01",
   )
   stage1.set_input("social_security", year, reduced_ss)
   ```
   Then recompute the same SS/HI income formulas from Stage 1 and define:
   - `remaining_ss_gap = stage1_ss_income - stage1_social_security`
   - `remaining_hi_gap = stage1_hi_income - medicare_expenditures`
5. Build the Stage-2 rate reform from the remaining gaps:
   - OASDI taxable payroll = `taxable_earnings_for_social_security`
   - HI taxable payroll = `payroll_tax_gross_wages`
   - If `remaining_ss_gap < 0`, `ss_rate_increase = abs(remaining_ss_gap) / oasdi_taxable_payroll`; otherwise 0.
   - If `remaining_hi_gap < 0`, `hi_rate_increase = abs(remaining_hi_gap) / hi_taxable_payroll`; otherwise `-remaining_hi_gap / hi_taxable_payroll`.
   - New employee/employer rates = current rates + half the corresponding rate increase.
   - Convert the rate dict with `Reform.from_dict(..., country_id="us")`; do not put a raw dict inside a reform tuple.
6. Define one helper used for ALL solvent sims:
   ```
   def solvent_sim(year, extra_reform=None):
       reforms = [_tax_assumption_reform(year), rate_reform_object]
       if extra_reform is not None: reforms.append(extra_reform)
       sim = dataset_microsimulation(
           {year}.h5,
           reform=tuple(r for r in reforms if r),
           start_instant=f"{year}-01-01",
       )
       sim.set_input("social_security", year, reduced_ss)   # SAME reduced_ss for every sim
       return sim
   ```
7. Solvent baseline income tax = `income_tax(solvent_sim(year))`; for each reform,
   delta = `income_tax(solvent_sim(year, reform)) - income_tax(solvent_sim(year))`.
   reduced_ss is computed from the BASELINE social_security and reused in both sims — never
   recompute it per-sim (the reform must not perturb the benefit base).

## [B2 cross-check — necessary because the gap-closes check is NOT sufficient]
A wrong-baseline run still closes its own gap to ~0, so that check cannot catch [B1]. Before
trusting any delta: assert the year-2035 current-law `base` reproduces the LIVE current-law
panel's 2035 baseline — compare `base` `tob_revenue_oasdi` and `income_tax` totals to the live
results.csv current-law 2035 baseline (within ~0.1%). If they don't match, STOP: the
stack/base is wrong. Do this as part of the 2035-only gate (below).

## [B3] HI expenditure vintage — resolved for this run
Historical option13 code read `data/hi_expenditures_tr2025.csv`, but the new
base is calibrated to **TR2026** (src/projection.py 16-19, 42-44;
`social_security_aux_tr2026.csv` carries hi_tob_* but NOT HI cost/expenditures).
Subtracting TR2025 Medicare expenditures from a TR2026 SS base is a silent
vintage mix on the single most important HI input.
- Decision: **use TR2026, no TR2025 fallback**. Build
  `data/hi_expenditures_tr2026.csv` from
  `data/sources/tr2026/HI Cost and Income Rates.csv` times the HI taxable payroll
  series, add both raw and derived files to `data/tr2026_sources.manifest.json`,
  and make `get_hi_data` read the TR2026 file.
- This is a conscious methodology call. Do not silently inherit TR2025. (Note:
  the reforms tax SS *benefits*, so the OASDI split is the headline; HI is the
  above-cap remainder, less sensitive — but the gap math still uses HI costs.)

## New-base wiring + Modal config
- Baselines: the certified manifest-backed `policyengine-us-data-long-term`
  Volume. Resolve the exact H5 **per year from the live static panel's
  `run_prefix`**, not from one hard-coded manifest. The current live panel uses
  `v2pop_tr2026_20260611` through 2070 and
  `v2pop_tr2026_noclone_20260612` for 2075+, so the balanced-fix recompute must
  map those run prefixes back to the matching baseline manifests before scoring.
  Load via `src.engine.dataset_microsimulation`. Decompose OASDI/HI for the
  OUTPUT rows via `src.reform_full_h5_worker.materialize_tob_revenue_pair`
  (consistent with the live panel); general_fund = revenue - oasdi - hi.
- Runtime: score under the same certified runtime recorded by the baseline H5
  metadata and live full-H5 cells (`policyengine==4.5.1`,
  `policyengine-us==1.700.2`, `policyengine-core==3.26.1`). Do not "upgrade"
  the balanced-fix worker to the repo-local/latest dev environment unless the
  live current-law [B2] cross-check is intentionally rebaselined; the 2035 gate
  caught a real ~0.5% OASDI TOB drift when the worker used `policyengine-us`
  1.729.0 against H5s built under 1.700.2.
- Years: **endpoints-first anchors only**: `2035`, `2050`, `2075`, `2100`.
  Interpolate the solvent/current-law ratio across intermediate years and apply
  it to the existing live current-law deltas. Spot-check one interpolated year
  against a direct compute; expand anchors only if the drift is material and
  report that decision.
- BEFORE fan-out: survey the manifest volume and assert each anchor year has the H5 plus
  its readiness sidecar (`{year}.h5.metadata.json`), that the H5 SHA matches the
  per-year resolved baseline manifest, and that H5 metadata's
  `policyengine_us.version` matches the Modal worker runtime; fail loudly if any
  is missing or stale (don't pay for a container that will score the wrong base).
- Modal function: cpu=4, **memory>=65536**, **timeout=10800-21600 (3-6h)**,
  **nonpreemptible=True**, retries=2. Detached. (The old script used memory=65536,
  timeout=21600 — these cells are heavy; do not inherit old short-cell assumptions.)
- Solvent-state handoff: the solvent baseline is a DERIVED scenario (current-law H5 + rate
  reform + set_input cut), not a storable input dataset — so each reform cell RE-DERIVES the
  solvent state via `solvent_sim` from `{year}.h5`. Persist the per-year solvent params
  (multiplier, 4 rates, gaps, gap_after) to the scores volume so a resumed run skips finished
  years and the output CSV can report them (matching the old `balanced_fix_baseline.csv` schema).

## Cost — estimate in SIMS, not cells; hard 2035-only gate
Each anchor needs: 1 current-law base sim + 1 Stage-1 benefit-cut sim + (for
the solvent baseline + each of 4 reforms) 5 `solvent_sim`s, i.e. **7 heavy
sims/anchor**, each triggering native double-branch TOB formulas (~10-15 min).
4 anchors -> **28 heavy sims**. PRINT the explicit sim count and estimate before
fan-out. **Run year 2035 ONLY first**: first run a current-law-only check, then
the full 2035 sentinel, verifying (a) both gaps close to ~0 after the fix, and
(b) the [B2] cross-check passes (2035 base matches the live panel). Only then
fan out 2050/2075/2100. Static only (no behavioral) unless the user asks.

## Dashboard surface restore (per-file git provenance — they differ)
- `balanced-fix-section.tsx`, `balanced-fix-data.ts`: restore from **`ceea4a2~1`** (newer,
  post-redesign, matches the balanced_fix_baseline.csv schema — prefer these).
- `option13-tab.tsx`, `option13-data.ts`: exist at `e077b66~1` (older generation — reference only).
- `git show e077b66~1:.../balanced-fix-section.tsx` will FAIL — use the right commit per file.
- Add a **Baseline scenario** control (values: "Current law" / "SS solvent"), default Current
  law. Name it so it does NOT collide with the existing trust-fund `allocationMode` selector,
  which already has an unrelated value labeled "Current law" (dashboard-shell.tsx ~796). Show
  the OASDI/HI/general-fund split for the solvency-baseline options. Design tokens; sentence-case.

## Verification (all must hold before declaring done)
- Both gaps close to ~0 after the fix (per year).
- [B2] cross-check: 2035 current-law base matches the live panel's 2035 baseline (~0.1%).
- OASDI + HI + general_fund == revenue_impact for every solvency cell.
- Live 14-reform results.csv numbers UNCHANGED (only ADD the solvency-baseline file/rows).
- `dashboard && bun run build` exits 0; `.venv/bin/pytest tests/ -q` green (incl. the pinned
  naming test); `ruff format`.
- Do NOT deploy, do NOT push, do NOT send email. Report: the solvency table (option1/2/8/12 at
  2035/2050/2075/2100 with OASDI/HI/general-fund), the [B3] vintage choice made, the actual sim
  count + Modal cost, gates passed/failed, and a short draft reply to Marc for #1/#2.

## Constraints
- Reuse existing functions (dataset_microsimulation, _tax_assumption_reform,
  materialize_tob_revenue_pair) and the self-contained 50/50 mechanics above —
  the rebuild's costly mistakes came from reinventing.
- Commit in logical chunks; do not push (user controls push).

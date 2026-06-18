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
- **General-fund column is ALREADY LIVE.** `scripts/build_dashboard_results.py` already computes
  `general_fund_impact = revenue_impact - tob_oasdi_impact - tob_medicare_hi_impact`
  (`add_general_fund_impact`) and validates reconciliation to 1e-8; `dashboard/public/data/
  results.csv` already carries the column and reconciles. VERIFIED 2026-06-18: existing
  columns zero-drift; Reverse Roth 2026 revenue -$46.81B = OASDI +$4.44B + HI +$53.37B +
  **general fund -$104.63B** (the above-the-line employee-OASDI payroll-tax deduction — this is
  the answer to Marc #3). Just confirm it's present and reconciles; **add nothing**.
- reverse_roth is answered by the current-law general-fund column ONLY. Do NOT score it against
  the solvent baseline (that would add a 5th, costlier reform for no ask).

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
`modal_batch/decomposition.py` (~line 91) and `modal_batch/run_panel.py` (~line 275) use
`current_law = _tax_assumption_reform(year)` (returns **None before 2035**;
`TAX_ASSUMPTION_START_YEAR = 2035` in src/pipeline.py).
- The old `batch/run_option13_modal.py` builds `Microsimulation(dataset=...)` with NO reform
  (~line 535). **Do not copy that.** On the new base it yields literal current-law SS
  thresholds, not the Trustees wage-indexed path the base was calibrated against, so every gap,
  TOB, multiplier, and rate would be silently wrong while still "closing to ~0".
- REQUIRED: build the baseline as
  `dataset_microsimulation({year}.h5, reform=_tax_assumption_reform(year))`
  and stack everything else on top of that current-law reform.

## [B2] Gap-closing as a hand-built two-sim delta (the benefit cut is a set_input)
The old Stage-1 benefit cut is NOT a parameter reform — it is
`sim.set_input("social_security", year, reduced_values)` after construction
(run_option13_modal.py ~625-629, 761-766). The Stage-2 rate increase IS a parameter reform
(OASDI + HI payroll rates). So the solvent baseline = current-law reform + rate reform +
set_input benefit cut. The cut **cannot** be a tuple component; the spec's old
`income_tax((solvent, reform))` one-liner is wrong. Construct explicitly:

1. `base = dataset_microsimulation({year}.h5, reform=_tax_assumption_reform(year))`.
2. From `base`, read `ss = base.calculate("social_security", year)` and compute the gaps
   (direct `.calculate(...).sum()` on `base` — these variables self-branch natively, so do NOT
   wrap them in materialize_tob_revenue_pair for the GAP math):
   - SS gap = (employee_ss_tax + employer_ss_tax + tob_revenue_oasdi) - ss_benefits
   - HI gap = (employee_hi_tax + employer_hi_tax + tob_revenue_medicare_hi) - medicare_expenditures
3. Derive, ONCE per year (port the exact 50/50 mechanics from run_option13_modal.py
   compute_option13_and_14_year): the benefit `multiplier`, `reduced_ss = ss * multiplier`, and
   the OASDI + HI rate increases (the `rate_reform` dict). Hold `reduced_ss` and `rate_reform`
   fixed for the whole year.
4. Define one helper used for ALL sims:
   ```
   def solvent_sim(year, extra_reform=None):
       reforms = [_tax_assumption_reform(year), rate_reform]
       if extra_reform is not None: reforms.append(extra_reform)
       sim = dataset_microsimulation({year}.h5, reform=tuple(r for r in reforms if r))
       sim.set_input("social_security", year, reduced_ss)   # SAME reduced_ss for every sim
       return sim
   ```
   (Confirm on year 2035 whether `start_instant` is needed for set_input to align arrays on the
   new base; the old script passed `start_instant=f"{year}-01-01"`.)
5. Solvent baseline income tax = `income_tax(solvent_sim(year))`; for each reform,
   delta = `income_tax(solvent_sim(year, reform)) - income_tax(solvent_sim(year))`.
   reduced_ss is computed from the BASELINE social_security and reused in both sims — never
   recompute it per-sim (the reform must not perturb the benefit base).

## [B2 cross-check — necessary because the gap-closes check is NOT sufficient]
A wrong-baseline run still closes its own gap to ~0, so that check cannot catch [B1]. Before
trusting any delta: assert the year-2035 current-law `base` reproduces the LIVE current-law
panel's 2035 baseline — compare `base` `tob_revenue_oasdi` and `income_tax` totals to the live
results.csv current-law 2035 baseline (within ~0.1%). If they don't match, STOP: the
stack/base is wrong. Do this as part of the 2035-only gate (below).

## [B3] HI expenditure vintage — DECISION REQUIRED before fan-out
`get_hi_data` reads `data/hi_expenditures_tr2025.csv` (run_option13_modal.py ~266), but the new
base is calibrated to **TR2026** (src/projection.py 16-19, 42-44; `social_security_aux_tr2026.csv`
carries hi_tob_* but NOT HI cost/expenditures). Subtracting TR2025 Medicare expenditures from a
TR2026 SS base is a silent vintage mix on the single most important HI input.
- PREFERRED: source the 2026 Medicare Trustees HI cost series -> add
  `data/hi_expenditures_tr2026.csv`, update `get_hi_data`. Cite the TR2026 table.
- FALLBACK (only if TR2026 HI costs are not readily available): keep TR2025 and record in the
  output metadata + the dashboard/paper footnote "HI gap uses TR2025 Medicare expenditures
  against a TR2026 SS base (approximation)."
- This is a conscious methodology call — surface it to the user; do not silently inherit TR2025.
  (Note: the reforms tax SS *benefits*, so the OASDI split is the headline; HI is the above-cap
  remainder, less sensitive — but the gap math still uses HI costs.)

## New-base wiring + Modal config
- Baselines: `crfb-baseline-builds` Volume, `/baselines/{year}.h5`. Load via
  `src.engine.dataset_microsimulation`. Decompose OASDI/HI for the OUTPUT rows via
  `src.reform_full_h5_worker.materialize_tob_revenue_pair` (consistent with the live panel);
  general_fund = revenue - oasdi - hi.
- Years: **2035, 2040, ..., 2100 (14 years)** — a subset of the 27 `default_selected_years()`
  (NOT "16"). The gap exists only 2035+ (pre-2035 `_tax_assumption_reform` is None -> no gap ->
  no solvency row; the dashboard simply shows no solvency data before 2035).
- BEFORE fan-out: survey `crfb-baseline-builds` (reuse run_panel.survey) and assert each of the
  14 years has `{year}.h5` + `.sentinel.json`; fail loudly if any is missing (don't pay for a
  container that will FileNotFoundError).
- Modal function: cpu=4, **memory>=65536**, **timeout=10800-21600 (3-6h)**,
  **nonpreemptible=True**, retries=2. Detached. (The old script used memory=65536,
  timeout=21600 — these cells are heavy; do not inherit decomposition.py's short-cell assumption.)
- Solvent-state handoff: the solvent baseline is a DERIVED scenario (current-law H5 + rate
  reform + set_input cut), not a storable input dataset — so each reform cell RE-DERIVES the
  solvent state via `solvent_sim` from `{year}.h5`. Persist the per-year solvent params
  (multiplier, 4 rates, gaps, gap_after) to the scores volume so a resumed run skips finished
  years and the output CSV can report them (matching the old `balanced_fix_baseline.csv` schema).

## Cost — estimate in SIMS, not cells; hard 2035-only gate
Each year needs: 1 current-law base sim + (for the solvent baseline + each of 4 reforms) a
`solvent_sim`, i.e. ~1 + 5 = ~6 heavy sims/year, each triggering native double-branch TOB
formulas (~10-15 min). 14 years -> ~84 heavy sims, realistically **$150-400** (the old
"$50-150 / 70-80 cells" was undercounted). PRINT the explicit sim count and confirm before
fan-out. **Run year 2035 ONLY first**: verify (a) both gaps close to ~0 after the fix, and
(b) the [B2] cross-check passes (2035 base matches the live panel). Only then fan out 2040-2100.
Static only (no behavioral) unless the user asks.

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
  materialize_tob_revenue_pair, the run_option13_modal 50/50 mechanics) — the rebuild's costly
  mistakes came from reinventing.
- Commit in logical chunks; do not push (user controls push).

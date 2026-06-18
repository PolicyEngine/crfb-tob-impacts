# Execution spec: recompute the Balanced Fix solvency baseline on the new certified base

Self-contained task spec. Goal: answer CRFB (Marc Goldwein, 2026-06-18) — score the
reform options against the **solvency baseline** (SS otherwise brought into balance),
with the OASDI / Medicare-HI / general-fund split, on the **new certified base** that the
live dashboard already uses. Plus restore the dropped balanced-fix dashboard surface and
add the general-fund column.

Repo: /Users/maxghenis/PolicyEngine/crfb-tob-impacts, branch v2-baseline-method.

## Background (read first)
- The reform panel was rebuilt on the new certified populace base (policyengine.py 4.17.5 /
  policyengine-us 1.729.0). Live dashboard: policyengine.org/us/taxation-of-benefits-reforms.
  The 14-reform static+behavioral results.csv is CORRECT and LIVE — DO NOT change it.
- The "solvency baseline" = the **Balanced Fix** (Option 13): a gap-closed SS/HI baseline,
  50% benefit cuts + 50% payroll-rate increases per year. It is NOT a Reform.from_dict; it's
  computed year-by-year. The original computation is `batch/run_option13_modal.py`
  (`compute_option13_and_14_year`, line ~311; `get_hi_data` for Medicare expenditures, ~259),
  but that script is wired to the OLD stack (pe-us 1.700.2, R2, the `5a35713` snapshot).
- The balanced-fix data + dashboard surface were dropped: data in commit `ceea4a2`
  ("Clean CRFB release artifacts"), surface in `e077b66` (the redesign). Recover the surface
  from git: `dashboard/src/components/balanced-fix-section.tsx`, `option13-tab.tsx`;
  `dashboard/src/lib/balanced-fix-data.ts`, `option13-data.ts`. Old data schema is in
  `git show ceea4a2~1:dashboard/public/data/balanced_fix_baseline.csv` (year, ss/hi gap,
  benefit_multiplier, rates, rate_increase revenue, tob_oasdi/hi impacts, gap_after, ...).

## Gap-closing mechanism (port to the new base; reuse, do not reinvent)
Per year (the gap exists once the Trustees tax assumption is active, i.e. 2035+):
- SS gap   = (employee_ss_tax + employer_ss_tax + tob_revenue_oasdi) - ss_benefits
- HI gap   = (employee_hi_tax + employer_hi_tax + tob_revenue_medicare_hi) - medicare_expenditures
- Close 50% of each gap with benefit cuts (Stage 1: scale benefits by a multiplier), then
  close the remaining 50% with payroll-rate increases (Stage 2: raise OASDI + HI rates).
- The solvent scenario = the new-base baseline with those benefit cuts + rate increases applied.
- Verify the gap closes to ~0 after applying (the old CSV's `*_gap_after_millions` is ~0).
Source of truth for the exact mechanics: `batch/run_option13_modal.py` + `get_hi_data`.

## New-base wiring (reuse modal_batch/run_panel.py + decomposition.py patterns)
- Baselines: `crfb-baseline-builds` Volume, `/baselines/{year}.h5` (the new certified-base
  Stage A-D years). Load via `src.engine.dataset_microsimulation` (NOT the old runtime_config).
- Decomposition (OASDI/HI): reuse `src.reform_full_h5_worker.materialize_tob_revenue_pair`
  (same function the new decomposition uses).
- Modal function: cpu=4, memory=65536, timeout=10800, **nonpreemptible=True**, retries=2
  (these cells are heavy + long — preemptible gets reclaimed mid-run; learned twice already).
- Years: 2035, 2040, ..., 2100 (14 years), matching the original balanced-fix panel.

## Reforms to score against the solvent baseline
Marc wants (his words → option ids):
- "Phased Roth" = **option12** (the meeting renamed Extended Roth -> Phased Roth; reforms.py
  still labels option12 "Extended Roth" — confirm/relabel as needed, but option12 is the one).
- "repeal" = **option1**
- "85% taxation" = **option2**, "100% taxation" = **option8** (do both unless told otherwise).
Score each as: income_tax((solvent_baseline, reform)) - income_tax(solvent_baseline), i.e. the
reform's INCREMENTAL effect once SS is already solvent — not vs current law.

## Decomposition (Marc #2 + #3 — three-way, totals reconcile)
For each (reform, year) against the solvent baseline, emit:
- tob_oasdi_impact, tob_medicare_hi_impact (from materialize_tob_revenue_pair),
- general_fund_impact = revenue_impact - tob_oasdi_impact - tob_medicare_hi_impact,
so OASDI + HI + general fund = total. (This is the general-fund line the 04/29 meeting asked
for; it's also what explains the Reverse Roth's general-revenue effect — the above-the-line
employee-OASDI payroll-tax deduction is a general-fund loss.)

## Also do now (no compute): general-fund column for the CURRENT panel
In `scripts/build_dashboard_results.py`, add `general_fund_impact = revenue_impact -
tob_oasdi_impact - tob_medicare_hi_impact` to every row, rebuild dashboard/public/data/
results.csv locally (no Modal), so the existing 14-reform panel already reconciles OASDI + HI
+ general fund. This directly answers Marc #3 for the Reverse Roth.

## Dashboard surface restore
Recover the balanced-fix surface from git (`git show e077b66~1:<path>`), adapt to the new data
and the current dashboard structure: a **baseline selector** (current law vs solvency baseline)
on the reform views, defaulting to current law. Show the OASDI/HI/general-fund split for the
solvency-baseline options. Match the live design tokens; sentence-case headings.

## Cost guardrails (post-incident discipline)
- Estimate before launching: ~14 years x (1 gap-closed baseline + 4 reforms) + endpoint
  decomposition ~= 70-80 nonpreemptible cells; print the count and confirm before fan-out.
- Behavioral/LSR for these solvency options, if requested, is ENDPOINT-ONLY (2035/2100
  multipliers interpolated) — never per-year. Default to static unless asked.
- Detached run; verify gaps close to ~0 on the first year before fanning out all years.

## Verification
- Gaps close to ~0 (`*_gap_after` ~ 0) after the balanced fix.
- Reform-vs-solvent deltas are sensible and signs match the current-law direction shaped by a
  solvent base (Phased Roth should look meaningfully better vs solvent than vs current law —
  the 04/29 note: employer contributions generate more revenue, lower benefit base reduces TOB
  losses).
- OASDI + HI + general_fund == revenue_impact for every cell (reconciles).
- Dashboard builds clean and the canonical URL serves the new solvency view; reply to Marc.

## Constraints
- Reuse existing functions (materialize_tob_revenue_pair, dataset_microsimulation, the gap
  mechanics) — the rebuild's mistakes came from reinventing.
- DO NOT change the live 14-reform results.csv numbers (only ADD the general_fund column +
  the new solvency-baseline rows/file).
- Commit in logical chunks; do not push (user controls push).
- Run `.venv/bin/pytest tests/ -q` green; `ruff format` before committing.

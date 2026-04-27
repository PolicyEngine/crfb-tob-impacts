# Fresh Review Brief

Use this brief to start an independent review of the CRFB taxation-of-benefits
release without relying on the prior chat history.

## Review Goal

Assess whether the current release boundary is methodologically sound:

- publish the cleaned static results as the current dashboard and paper surface
- call the labor-supply-response track `conventional`, not `dynamic`
- quarantine conventional point estimates until they are rerun on the same
  baseline lineage as the static release

The review should verify that this boundary follows from the artifacts, not from
the previous session's assertions.

## Current Working State

Relevant repo:

- `/Users/maxghenis/PolicyEngine/crfb-tob-impacts`

Primary current static artifacts:

- `results/all_static_results_latesthf_2026_2100_14options.csv`
- `dashboard/public/data/all_static_results.csv`
- `dashboard/public/data/option13_balanced_fix.csv`
- `dashboard/public/data/trustees_vs_pe_gaps_comparison.csv`

Conventional artifact with historical filename:

- `results/all_dynamic_results_latesthf_2026_2100_standard_options.csv`

The `all_dynamic_*` filenames are compatibility names only. Public-facing text
should call this track `conventional`. While the baseline mismatch remains, the
conventional artifact should not be copied into `dashboard/public/data`, built
dashboard output, `.vercel-site`, or rendered paper exhibits.

Current validation guard:

- `scripts/publish_conventional_results.py` refuses to publish conventional
  results if baseline levels differ from the static reference.
- `scripts/generate_paper_conventional_exhibits.py` refuses to generate citable
  conventional exhibits under the same condition.
- `tests/test_release_artifacts.py` checks that the conventional artifact is not
  claimed comparable or exposed through public release artifacts while its
  baseline differs from the static release.

Known conventional/static mismatch from the latest check:

- `baseline_revenue`: max difference about `$23,465B` at `option1`, `2100`
- `baseline_tob_medicare_hi`: max difference about `$582B` at `option1`, `2100`
- `baseline_tob_oasdi`: max difference about `$1,254B` at `option1`, `2100`
- `baseline_tob_total`: max difference about `$1,836B` at `option1`, `2100`

Because of that mismatch, the current documentation says conventional results
are quarantined pending a same-baseline rerun.

## Client Email Context

Anthony Colavito emailed on April 24, 2026 at 10:55 AM ET in the CRFB contract
thread (`194b3b7be8a76d89`). The message is in the inbox and marked important.

He wrote that he was reviewing the dashboard and wondered whether a couple of
options were not rendering under `Balanced Fix Baseline`. He specifically wants
to see how the Roth options perform under the solvency baseline versus current
law, because the solvency baseline changes payroll-tax rates and benefit levels
and therefore changes the revenue raised under the Roth swap.

Current code/data state related to that email:

- `dashboard/public/data/all_static_results.csv` includes both `option13` and
  `option14_stacked` for `2026-2100`.
- `dashboard/src/lib/reforms.ts` includes `option14_stacked`.
- `dashboard/src/components/dashboard-shell.tsx` puts `option14_stacked` in the
  main `Structural swaps` navigation.
- `dashboard/src/components/option13-tab.tsx` shows the balanced-fix baseline
  mechanics, but it does not itself show Roth-under-balanced-baseline option
  comparisons.

So Anthony's concern may be a UX/rendering issue rather than a missing-data
issue. A fresh review should decide whether `option14_stacked` in the main
structural-swap list is enough, or whether the Balanced Fix tab should include a
dedicated comparison of current-law Roth options versus balanced-fix Roth
results.

## Files To Inspect First

- `docs/current/methodology.md`
- `docs/current/deliverables.md`
- `paper/sections/03-methods.qmd`
- `paper/sections/04-results-and-validation.qmd`
- `paper/sections/05-results-framework.qmd`
- `paper/sections/06-publication-boundary.qmd`
- `paper/sections/exhibits/conventional-results.md`
- `dashboard/src/components/methodology-section.tsx`
- `dashboard/src/lib/reforms.ts`
- `scripts/build_latesthf_14option_delivery.py`
- `scripts/publish_conventional_results.py`
- `scripts/generate_paper_conventional_exhibits.py`
- `tests/test_release_artifacts.py`

## Independent Review Questions

1. Does the static release actually use one coherent Trustees-lineage baseline
   across `option1` through `option12` and the assembled `option13` /
   `option14_stacked` rows?
2. Is `option14_stacked` correctly measured relative to the `option13`
   balanced-fix baseline, using recovered special-case raw rows rather than an
   incompatible splice from standard `option12`?
3. Does the dashboard, paper, and documentation avoid citing conventional point
   estimates while the conventional baseline mismatches the static baseline?
4. Are the conventional guard scripts strict enough to fail closed until the
   same-baseline rerun exists?
5. If conventional results are needed, what is the smallest rerun scope that
   produces a same-baseline standard panel for `option1` through `option12`?
6. Should `option13` and `option14_stacked` remain static-only, or is there a
   client need strong enough to justify a separate iterative conventional
   balanced-fix solve?
7. Are the comparison spreadsheet and dashboard artifacts cleanly separated so
   legacy reference values cannot leak into current dashboard data?
8. Does the dashboard answer Anthony's April 24 request about Roth options under
   the Balanced Fix baseline, or should the UI add a dedicated balanced-fix Roth
   comparison panel?

## Suggested Verification Commands

Run these from `/Users/maxghenis/PolicyEngine/crfb-tob-impacts`:

```bash
git status --short
pytest -q tests/test_release_artifacts.py
python scripts/publish_conventional_results.py
python scripts/generate_paper_conventional_exhibits.py
```

The last two commands should currently fail with `Conventional baseline does
not match the static reference`. If they succeed without a same-baseline rerun,
that is a release-boundary bug.

To reproduce the baseline comparison directly:

```bash
python - <<'PY'
import pandas as pd

static = pd.read_csv("results/all_static_results_latesthf_2026_2100_14options.csv")
conv = pd.read_csv("results/all_dynamic_results_latesthf_2026_2100_standard_options.csv")
cols = [
    "baseline_revenue",
    "baseline_tob_medicare_hi",
    "baseline_tob_oasdi",
    "baseline_tob_total",
]
merged = conv[["reform_name", "year", *cols]].merge(
    static[["reform_name", "year", *cols]],
    on=["reform_name", "year"],
    suffixes=("_conventional", "_static"),
)
for col in cols:
    diff = (merged[f"{col}_conventional"] - merged[f"{col}_static"]).abs()
    row = merged.loc[diff.idxmax()]
    print(col, diff.max(), row["reform_name"], int(row["year"]))
PY
```

## Prompt For A Fresh Session

```text
Review /Users/maxghenis/PolicyEngine/crfb-tob-impacts from scratch as if you
had not seen the prior chat. The core question is whether the CRFB
taxation-of-benefits release boundary is correct: publish static results now,
call the labor-supply-response track "conventional" rather than "dynamic", and
quarantine conventional point estimates until a same-baseline rerun exists.

Do not assume the current docs are right. Verify from artifacts and code.
Inspect docs/current/methodology.md, docs/current/deliverables.md,
paper/sections/03-methods.qmd, paper/sections/04-results-and-validation.qmd,
paper/sections/05-results-framework.qmd,
paper/sections/exhibits/conventional-results.md,
dashboard/src/components/methodology-section.tsx,
dashboard/src/lib/reforms.ts, scripts/build_latesthf_14option_delivery.py,
scripts/publish_conventional_results.py,
scripts/generate_paper_conventional_exhibits.py, and
tests/test_release_artifacts.py.

Answer these questions:
1. Are the static artifacts internally coherent and suitable as the current
   public release surface?
2. Is the conventional artifact correctly quarantined, and do the publish/paper
   scripts fail closed on the current baseline mismatch?
3. Is "conventional" the right public label, with "dynamic" remaining only as
   historical internal filenames where necessary?
4. Did any dashboard, paper, or spreadsheet artifact still cite conventional
   point estimates unsafely?
5. If a rerun is needed, what exactly should be rerun, for which reforms and
   years, and what validation should pass before publishing?
6. Anthony Colavito emailed on April 24, 2026 asking whether some Roth options
   were missing under "Balanced Fix Baseline." Does the dashboard currently
   answer that request? Check whether option14_stacked is visible and
   understandable, and whether a dedicated balanced-fix Roth comparison should
   be added.

Run at minimum:
pytest -q tests/test_release_artifacts.py
python scripts/publish_conventional_results.py
python scripts/generate_paper_conventional_exhibits.py

The last two commands should fail until conventional and static baselines
match. If they do not, identify why.
```

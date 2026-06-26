# Budget-window anchor infill — reproducibility record

This record documents the targeted interpolation correction applied to the
published reform panel for the budget-window years, and the exact-version
reproduction it required. It is intentionally explicit about the messy parts:
the published panel is on an older build than the repository head, so the infill
years had to be reproduced from a pinned worktree, validated against the
published cells before being merged.

## Problem

Reforms are scored at exact anchor years (`2026`, `2030`, then every fifth year
`2035`–`2100`) and intermediate years are linearly interpolated. OBBBA's
temporary Schedule 1-A deductions (enhanced senior deduction; tip, overtime, and
auto-loan-interest exclusions) apply through `2028` and lapse in `2029`, and the
SALT cap reverts after `2029`. Linear interpolation across the `2026`→`2030` gap
smears that step. `option7` (repeal the senior deduction only) must fall to ~`$0`
from `2029` because the deduction is already gone from current law, but the
interpolated panel shows it gliding down across `2026`–`2030`, misstating the
budget-window years by up to ~`$11B`. `option4` and `option11` (which also repeal
the senior deduction) carry the same error.

## Fix

Add exact anchors only where the schedule bends:

- **`2028` + `2029`** — bracket the temporary-deduction sunset (end of 2028) and
  the SALT reversion (end of 2029). Applies to all 14 reforms.
- **`option6` `2032` + `2033`** — its employer-payroll-tax inclusion phases in
  annually and caps at `2033`; these bracket that corner.

`option5`, `reverse_roth` (immediate) and `option12` (smooth straight-line ramp)
need no extra anchors. Total infill = 14 × {2028, 2029} + option6 × {2032, 2033}
= **30 cells**.

## Version pins — MUST match the published panel

| Component | Pin |
|---|---|
| populace base | `populace-us-2024-9f1260b-20260611`; HF dataset commit `68be080e70b3`; file sha256 `dc75c0d4fdedd57946db84a8d838dbc5b61a284365c3ce6eb6508b8e81111a4b` (local `data/sources/populace/populace_us_2024.h5`) |
| policyengine-us | `1.700.2` |
| policyengine.py | `4.5.1` (editable; `_worktrees/policyengine-py-crfb-longrun-full` @ `2750c83c`) |
| crfb-tob-impacts | commit `3de8abb6` (NOT head) |

**Why not head.** Head (`a0e58549`) carries commit `3dcdce5`, which added
income-tax calibration ("income guards") to the projection; head builds a
baseline ~12% below the published one ($2,849B vs $3,232B at 2030). It is the
*more* income-tax-accurate successor, but it is not the version the published
panel was built on, so infilling there would create a seam. The infill is a
correction on the existing panel, not a rebuild.

## Reproduction recipe

```bash
# 1. Worktree at the certified commit. Place it UNDER ~/PolicyEngine so the
#    editable ../_worktrees/policyengine-py-... path resolves.
git worktree add ~/PolicyEngine/crfb-cert 3de8abb6
cd ~/PolicyEngine/crfb-cert
uv sync --frozen                         # -> pe-us 1.700.2, policyengine.py 4.5.1

# 2. Build the 4 infill baselines + a 2030 smoke control, on the 9f1260b base.
#    (Run one process per year in parallel; the build is local, not Modal.)
.venv/bin/python scripts/build_v2_projected_datasets.py \
    --years 2030 \
    --base-dataset ~/PolicyEngine/crfb-tob-impacts/data/sources/populace/populace_us_2024.h5 \
    --output-dir projected_datasets_certrepro
# ... repeat for 2028, 2029, 2032, 2033

# 3. BUILD GATE — 2030 baseline income tax must reproduce the published value
#    $3,231.9B to ~0% (observed: 0.00%). If off, the env is wrong; stop.

# 4. SCORING SENTINEL — re-score published-year cells on the rebuilt 2030 baseline
#    and require they reproduce the published impacts to the dollar:
#      option1 -159.411B   option7 0.000B   option8 93.725B   (all observed exact)

# 5. Baseline manifest for the infill years.
.venv/bin/python scripts/build_v2_baseline_manifest.py \
    --dataset-dir projected_datasets_certrepro \
    --run-id crfb-9f1260b-certinfill --created-at 2026-06-25T00:00:00Z \
    --output docs/current/manifests/baseline-dataset-manifest-9f1260b-certinfill.json

# 6. Score the 30 cells via the certified full-H5 worker (src.reform_full_h5_worker
#    .run_reform_full_h5_cell, require_object_store=False), from the worktree, batched.
#    Produces the same full-H5 artifacts the published cells have. Upload to R2
#    (axiom-corpus, crfb/reform_full_h5/<run_prefix>/...) for lineage.

# 7. Re-aggregate results.csv: add 2028/29/32/33 as exact anchors and re-interpolate.
```

## Why the certified worktree end to end (not Modal with head)

The Modal full-H5 image mounts the *current* repository, so a standard Modal run
would score with head's drifted code. For 13 of 14 reforms that drift is cosmetic
(a `conventional`→`behavioral` rename) plus guard/logging changes, but
`reverse_roth`'s payroll-deduction definition changed substantively. Scoring all
30 cells from the pinned worktree removes that open question entirely and produces
identical full-H5 lineage artifacts, while also avoiding the Modal spend.

## Seam gates — observed

- **Build gate.** Rebuilt 2030 baseline income tax `$3,231.9B` vs published
  `$3,231.9B` — `0.00%` deviation.
- **Scoring sentinel @2030.** `option1` `−159.411B`, `option7` `0.000B`,
  `option8` `93.725B` — each equal to the published value to the dollar.

Both gates passing certifies that base, build code, model version, and scoring
code all match the published panel, so the four budget-window anchors sit exactly
on the published trajectory with no discontinuity.

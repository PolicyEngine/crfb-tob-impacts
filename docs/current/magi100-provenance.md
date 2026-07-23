# magi100 (full MAGI inclusion) scoring provenance

CRFB (Anthony Colavito, 2026-07-06) requested an option counting 100% of
Social Security benefits, rather than 50%, in the combined income that
determines the taxable share of benefits.

## Reform

`gov.irs.social_security.taxability.combined_income_ss_fraction` = 1.0 for
2026-2100 (`src/reforms.py::get_magi100_dict`). The parameter exists in the
certified policyengine-us 1.700.2, so the option is a pure parameter reform.

## Certified environment and gates

Scored 2026-07-06/07 on the certified-reproduction environment from
`budget-window-infill.md` (worktree at `3de8abb6`, `uv sync --frozen` →
policyengine-us 1.700.2 + policyengine 4.5.1 editable, populace 9f1260b base,
datasets rebuilt with `build_v2_projected_datasets.py --base-dataset
data/sources/populace/populace_us_2024.h5`). Gates, in order:

1. Rebuilt 2030 baseline income tax reproduced the published $3,231.9B
   (observed 0.0010%).
2. Sentinel rescore of published cells on the rebuilt 2030 dataset via
   `run_v2_local_proof.py`: option1 -159.411B, option7 0.000B, option8
   +93.725B — all reproduced to <= $0.3M.

magi100 was then scored at the 18 production anchor years (2026, 2028-2030,
every fifth year 2035-2100) with the same per-cell worker
(`run_reform_full_h5_cell`, `require_object_store=False`); scenario.h5 +
metadata artifacts under `tmp/full_h5_magi100/magi100_certrepro_20260706/`.

## Same-family baselines (far-horizon drift)

The rebuilt datasets reproduce the published family to ~0.00% through 2070
but drift +4.5-5.9% on baseline income tax at 2075-2100 (far-horizon
calibration is best-effort per `v2-baseline-method.md`). Pairing rebuilt
reform legs with PUBLISHED baselines therefore inflates far-year impacts by
the drift; an initial assembly with that pairing produced impacts violating
the structural upper bound (magi100 <= option2, the 85%-for-all option) and
was discarded. Published magi100 rows instead use baselines computed from
the SAME rebuilt datasets (`src.year_runner.load_baseline`), the convention
the 2026-06 budget-window infill used for its published cells
(`scripts/magi100_gate_aggregate.py`, modes `baselines` / `rows2`).

## Validation and assembly

- magi100 <= option2 holds at every anchor year (structural bound: the
  option accelerates threshold crossing under the same 85% cap).
- Anchor path is smooth: +$10.6B (2026) -> +$21.8B (2030) -> +$71.0B (2070)
  -> +$161.3B (2100); 10-year nominal +$200.6B; 75-year PV +$812.0B at the
  Trustees effective rates.
- `scripts/assemble_magi100_results.py` scales to billions, linearly
  interpolates non-anchor years (panel convention), and refuses partial
  assembly; rows carry `run_prefix=magi100_certrepro_20260706`.

Distributional deciles published 2026-07-18 (with tax_panel_2005's) via the
same-family pairing: certrepro reform-leg H5s against per-household
baselines exported from the certified worktree
(`scripts/export_certrepro_baseline_households.py` +
`scripts/build_distributional_data.py`). All-decile losses concentrated in
the middle (deciles 4-7), matching the threshold-crossing mechanism; decile
sums mirror the certified revenue impacts within ~1-6%.

## Far-anchor family fix (2026-07-22)

The 2075–2100 anchors were rescored on the published no-clone datasets
(run prefix `noclone_farfix_20260722`; see
docs/current/tax-panel-2005-provenance.md for the donor-clone diagnosis
and the option2@2075 exact sentinel). The certrepro worktree's far-year
datasets carried 32,000 donor-clone households, mismatching the
published panel's no-clone far family and producing a small 2070→2075
step (+$71.0B → +$69.3B). Post-fix path: +$71.0B (2070) → +$88.3B
(2075) → +$217.4B (2100), smooth; 75-year PV at the Trustees effective
rates +$877.1B under the dashboard display convention (statutory-split
sum +$854.4B = OASDI +$188.5B / HI +$666.0B; was +$812.0B on the cloned
far years). Anchors ≤2070
and the 10-year window are unchanged.

# tax_panel_2005 (2005 Tax Panel simple deduction) scoring provenance

CRFB (Anthony Colavito, 2026-07-17) requested a variation of the President's
Advisory Panel on Federal Tax Reform (2005) Social Security recommendation
(report pp. 87-89): replace the current benefit-taxation thresholds with a
simple deduction, without the Panel's inflation indexing. Per the report's
Figure 5.11 worksheet:

    taxable SS = clamp(50% x (income - threshold), 0, 85% x benefits)

with income counting 85% of benefits (worksheet line 9 includes line 7) and
thresholds of $22,000 single / $44,000 joint, fixed in nominal terms.

## Reform

Pure parameter reform (`src/reforms.py::get_tax_panel_2005_dict`), all
parameters present in the certified policyengine-us 1.700.2:

- `combined_income_ss_fraction` 0.5 → 0.85 (worksheet income measure),
- `rate.base.benefit_cap` 0.5 → 0.85 (phase-in runs to the 85% cap),
- `rate.base.excess` unchanged at 0.5 (the worksheet's 50% slope is current
  law's tier-1 rate),
- `threshold.base.main` → $22,000 (single, head of household, surviving
  spouse, separate) / $44,000 (joint), constant 2026-2100 (unindexed),
- `threshold.adjusted_base.main` → $10B for all main statuses (second tier
  unreachable; `rate.additional.*` therefore inert),
- separate-cohabitating thresholds untouched (current-law $0; the Panel is
  silent on that anti-abuse rule).

Interpretation choices, stated in the dashboard mechanism note: the income
measure keeps the current-law combined-income construction (modified AGI plus
tax-exempt interest) with the benefit fraction raised to 85%, matching the
worksheet's total-income line; head of household and surviving spouse map to
the single threshold (the Panel's system had only unmarried/married).

A four-case unit test (`tests/test_reforms.py::test_tax_panel_2005_matches_worksheet`)
asserts the reform reproduces the Figure 5.11 worksheet to the dollar for
phase-in-binding, cap-binding, below-threshold, and joint cases.

## Certified environment and gates

Scored 2026-07-17 on the same certified-reproduction environment as magi100
(`docs/current/magi100-provenance.md`): worktree `~/PolicyEngine/crfb-cert`
at `3de8abb6`, policyengine-us 1.700.2 + policyengine.py 4.5.1, populace
9f1260b base, the 18 anchor datasets in `projected_datasets_certrepro/`
byte-identical to the magi100 run (manifest
`baseline-manifest-tax-panel-2005.json` shas equal the magi100 manifest's).
The worktree's `src/reforms.py` patch is byte-identical to the committed
head definition (verified by diff). Gates, in order:

1. Baseline check: the cached certrepro 2030 baseline income tax reproduces
   the published $3,231.9B (cache from the magi100 run; datasets unchanged
   by sha).
2. Scoring sentinel rescore at 2030 (fresh, with the patched reforms.py
   loaded): option1 −159.411B (diff 0.0M), option7 0.000B (diff 0.0M),
   option8 +93.725B (diff 0.3M) — all within the ≤$0.3M tolerance against
   published values.

tax_panel_2005 was then scored at the 18 production anchor years (2026,
2028-2030, every fifth year 2035-2100) with the same per-cell worker
(`run_reform_full_h5_cell`, `require_object_store=False`); scenario.h5 +
metadata artifacts under
`tmp/full_h5_tax_panel_2005/tax_panel_2005_certrepro_20260717/`.

## Same-family baselines

Rows pair the certrepro reform legs with baselines computed from the SAME
rebuilt datasets (the magi100 lesson: published-baseline pairing inflates
far-horizon impacts by the +4.5-5.9% 2075-2100 drift). The per-year baseline
cache `tmp/magi100_certrepro_baselines.json` is reform-independent and reused
directly (`scripts/tax_panel_2005_aggregate.py`).

## Validation and assembly

- Structural bound: tax_panel_2005 <= option2 (the 85%-for-all option) at
  every anchor year — any regime capped at 85% of benefits raises weakly
  less than taxing 85% for everyone. Enforced by the aggregation script;
  holds at all 18 anchors (impacts are negative, option2's positive).
- Anchor path (post far-anchor fix, below): −$1.9B (2026) → −$2.7B
  (2030) → −$58.8B (2070) → −$75.6B (2075) → −$141.1B (2100), smooth
  through the far-horizon boundary.
- `scripts/assemble_tax_panel_2005_results.py` scales to billions, linearly
  interpolates non-anchor years (panel convention), refuses partial
  assembly; rows carry `run_prefix=tax_panel_2005_certrepro_20260717`.
- Artifact lineage: `scripts/upload_tax_panel_2005_r2.py` uploads each
  cell's scenario.h5 + metadata.json to
  `r2://axiom-corpus/crfb/reform_full_h5/tax_panel_2005_certrepro_20260717/...`
  and records URIs + output H5 sha256 in `tmp/tax_panel_2005_lineage.json`.

Distributional deciles published 2026-07-18 (with magi100's): the certrepro
reform-leg H5s are diffed against per-household baselines exported from the
certified worktree on the same rebuilt datasets
(`scripts/export_certrepro_baseline_households.py` →
`scripts/build_distributional_data.py --reforms magi100,tax_panel_2005`,
per-reform merge). Decile net-income sums mirror the certified revenue
impacts within ~1-6% (state-tax and benefit knock-ons inside household net
income). 2026 shape: losses in deciles 1-5 (taxation starts at lower
non-benefit income), gains in 6-10 (the 50% phase-in undercuts the 85%
second tier).

## Headline results

Roughly revenue-neutral in the budget window, a growing loss thereafter
(figures post far-anchor fix): −$1.9B (2026), −$36.5B over 2026–2035
nominal, −$141.1B by 2100; 75-year total −$4,271.5B undiscounted.
Present value at the Trustees effective rates (per-fund discounting,
panel convention): −$546.0B under the dashboard's default
baseline-shares split; summing the statutory-split tiers instead gives
−$524.5B (OASDI +$40.1B, HI −$564.6B) — the gap is the two splits
discounting different fund shares at different rates.

Under the statutory (current-law) trust-fund split the loss is almost
entirely Medicare HI's: the 50%-per-dollar phase-in reaches the 85% cap
far more slowly than current law's 85% second-tier rate, shrinking the
above-50%-of-benefits region, while OASDI gains slightly for most of the
horizon (the lower entry point pulls additional lower-income units into
the below-50% tier). The 75-year PV decomposition: OASDI +$40.1B, HI
−$564.6B.

The near-zero budget-window net is consistent with the 2005 Panel's own
revenue-neutral framing; the widening later loss is the unindexed 50%
phase-in lagging current law's faster tier-2 saturation as wage growth
concentrates retirees in that band.

## Far-anchor family fix (2026-07-22)

CRFB (Anthony Colavito) spotted a step at 2070→2075 (−0.035% → −0.020%
of GDP). Root cause: the pinned certification worktree predates the
donor-clone deletion — `DONOR_CLONE_START_YEAR = 2075` in its
v2_pipeline adds 32,000 cloned households (4,000 donors × 8) to the
2075–2100 datasets (107,112 records vs 75,112 at 2070), spreading the
same aggregate benefits across more, smaller units and pushing the
at-85%-cap share from 41% to 53% — while the published panel's far
anchors use the no-clone family. The seam was an inconsistency between
the two certrepro-scored reforms and the rest of the panel, not a
property of the published methodology.

Fix: both reforms' 2075–2100 anchors rescored on the published no-clone
datasets (local `projected_datasets_v2pop/{2075..2100}.h5`,
sha-verified against
`docs/current/manifests/baseline-dataset-manifest-v2pop-noclone.json`),
run prefix `noclone_farfix_20260722`, certified env (pe-us 1.700.2).
Gate: option2@2075 rescored on the same dataset reproduces the
published +$103.4174B to the dollar, proving env + family + the
published-baseline pairing. Anchors ≤2070 unchanged; rows re-spliced
and re-interpolated (`scripts/fix_far_anchor_family.py`); cells on R2
under the new prefix. 2075 anchor: −$41.2B (cloned) → −$75.6B
(no-clone), on-trend from 2070; the late-century flattening in %-of-GDP
terms (−0.037% → −0.028% by 2100) is the genuine 85%-cap saturation.
Headline updates: 75-year −$4,271.5B undiscounted; statutory-split PV
−$524.5B (OASDI +$40.1B / HI −$564.6B). The 10-year window is
unaffected. Far-year deciles rebuilt against no-clone per-household
baseline exports (`crfb-cert/tmp/baseline_households_noclone/`).

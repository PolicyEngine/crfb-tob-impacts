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
- Anchor path is smooth within each dataset family: −$1.9B (2026) →
  −$2.7B (2030) → −$58.8B (2070) → −$88.8B (2100), with the known
  2070→2075 far-horizon family seam (−$58.8B → −$41.2B) matching the
  published magi100 series' seam at the same years (+$71.0B → +$69.3B).
  Certrepro baseline drift vs published: 0.00% through 2070, +4.5–5.9%
  at 2075–2100 — the same-rebuild pairing neutralizes it.
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

Roughly revenue-neutral in the budget window, a growing loss thereafter:
−$1.9B (2026), −$36.5B over 2026–2035 nominal, −$88.8B by 2100;
75-year total −$2,932B undiscounted. Present value at the Trustees
effective rates (per-fund discounting, panel convention): −$440B under the
dashboard's default baseline-shares split; summing the statutory-split
tiers instead gives −$435B (OASDI +$40.3B, HI −$475.4B) — the small gap is
the two splits discounting different fund shares at different rates.

Under the statutory (current-law) trust-fund split the loss is entirely
Medicare HI's: the 50%-per-dollar phase-in reaches the 85% cap far more
slowly than current law's 85% second-tier rate, shrinking the
above-50%-of-benefits region (HI −$3.1B in 2026 to −$88.6B in 2100), while
OASDI gains slightly for most of the horizon (+$1–2B/year through
mid-century — the lower entry point pulls additional lower-income units
into the below-50% tier) before fading to about zero by 2100. The 75-year
PV decomposition: OASDI +$40.3B, HI −$475.4B.

The near-zero budget-window net is consistent with the 2005 Panel's own
revenue-neutral framing; the widening later loss is the unindexed 50%
phase-in lagging current law's faster tier-2 saturation as wage growth
concentrates retirees in that band.

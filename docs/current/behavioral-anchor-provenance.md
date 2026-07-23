# Behavioral completion anchors and sign-flip interpolation (H-01b)

## Why

Behavioral display rows derive from behavioral/static ratios computed at
exact full-H5 behavioral cells and interpolated across years. Through
2026-07-22 the only exact behavioral cells were the 2026/2100 endpoints
(`lsrfix_behavioral_20260719`), so a single ratio segment spanned the
whole horizon. Two structural problems with that, both exposed by the
2026-07 audit's completion-anchor work:

1. **Policy kinks.** option12's phase-out completes in 2062 (operative
   settings identical to option5 from then on); a single 2026→2100 ratio
   segment cannot bend there, so the two reforms' behavioral rows
   diverged mid-century even though the policies coincide.
2. **Static sign flips.** The structural swaps' static revenue crosses
   zero mid-century (option5: +$48.7B in 2026 → −$547.8B in 2100). A
   behavioral/static ratio is meaningless across that crossing, and
   interpolating it produced mid-century behavioral values with no
   relation to the truth.

## Cells

Three behavioral cells, run prefix `anchor_behavioral_20260723`,
certified worktree (policyengine-us 1.700.2 + the documented #521
delete_arrays backport, verified applied before launch), certrepro
datasets (2062.h5, 2033.h5 — the 2033 file is byte-identical to the June
certinfill dataset), baselines from the same-dataset static caches (the
lsrfix flow verified behavioral baseline legs equal static baselines to
ten decimals):

- `option12@2062`: −$112.999025B (static −$58.278146B) — the labor
  response roughly doubles the mid-century cost; the prior
  ratio-interpolated row showed −$61.77B.
- `option5@2062`: −$112.999025B — scored independently as the
  **convergence gate**; agrees with option12 to the dollar (gap
  0.000M), as the identical operative settings require. Both reforms'
  behavioral rows are now identical from 2062 through 2100.
- `option6@2033`: +$148.4313B (static +$176.9135B, bracket-capped dict —
  the cell was launched after the capped definition was restored and
  imports the fixed builder).

option6's dict used the bracket-capped definition
(`option6_bracketfix_20260723` static counterpart); the option12/option5
dicts are unchanged by that fix.

## Publisher changes

`publish_behavioral_endpoint_dashboard_results.py`:

- ratio interpolation generalized from the fixed endpoint pair to
  piecewise segments over every exact behavioral anchor per reform
  (bit-identical output on endpoint-only reforms; unit tests pin the
  segment mechanics in `tests/test_behavioral_anchor_interpolation.py`);
- segments whose static anchor values have opposite signs interpolate
  the behavioral **values** directly instead of ratios, with a
  per-segment record in the publication metadata;
- new interpolation prefix `behavioral_anchor_ratio_interpolation_20260723`
  on all 1,019 interpolated rows (31 exact rows keep their cell
  prefixes).

The paper's results section describes the piecewise + sign-flip method;
the contract records per-reform behavioral interpolation parents. Cell
artifacts (scenario.h5 + metadata.json ×3) uploaded to
`r2://axiom-corpus/crfb/reform_full_h5/anchor_behavioral_20260723/…`.

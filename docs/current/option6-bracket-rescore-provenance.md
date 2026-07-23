# option6 bracket-cap rescore and the pooled baseline series (M-06, M-01)

## The defect (audit M-06)

`get_option6_dict` (and its behavioral variant) wrote option6's descending
phase-down schedule to all three `rate.additional` parameters — including
`bracket`, the coefficient on the 50-85% tier, which is 0.50 under current
law (IRC section 86(a)(2)(A)(ii)) and is not part of the 85% family. In
2029-2034 the schedule's values exceed 0.50 (0.80 descending to 0.55), so
scored cells taxed the second tier above statute; from 2035 (value 0.50)
the excess vanishes and published cells are unaffected. The dict builders
now cap the bracket at its current-law 0.50 in both repos.

## Datasets

The affected exact anchors are 2029/2030 (existing certrepro datasets) and
2032/2033 (rebuilt 2026-07-23 with `build_v2_projected_datasets.py` in the
certified worktree). The rebuilt 2032/2033 H5s are **byte-identical** to
the June certinfill datasets recorded in
`baseline-dataset-manifest-9f1260b-certinfill.json` (sha256
`fd518c83…`/`95f940e4…`), as are the existing 2028-2030 certrepro files —
the dataset build is deterministic across platforms, so the rescore runs
on the same bytes the original cells used. Directory manifest:
`baseline-manifest-anchor2032-2033.json` (run-id
`crfb-9f1260b-anchor2032-2033`), registered as a contract supplemental in
`docs/current/manifests/` (supersedes the anchor2062 manifest's coverage;
all overlapping year shas equal).

## Cells and gates

Run prefix `option6_bracketfix_20260723`, certified env (policyengine-us
1.700.2), local worker, manifest validation fail-closed. Baselines:
2029/2030 from the magi100-era certrepro cache; 2032/2033 computed fresh
(`tmp/anchor2032_2033_baselines.json`, on R2). Gates
(`scripts/fix_option6_bracket_rescore.py gate`), all passed 2026-07-23:

- **G2 family bridge** — option6 scored with the OLD (uncapped) dict on
  the same datasets reproduces the published certinfill values:
  2029 +90.883931B vs published +90.883933B (drift −0.002M);
  2032 +160.629732B vs +160.629735B (drift −0.003M). The env cannot
  masquerade as, or hide inside, the bracket fix. Bridge cells kept on R2
  under `option6_bridge_olddict_20260723`.
- **G3 direction** — the capped rescore is below the published value at
  every affected anchor: 2029 −$2.862B, 2030 −$2.127B, 2032 −$1.027B,
  2033 −$0.593B — shrinking monotonically as the schedule's bracket value
  descends toward the 0.50 cap.

Splice: exact rows replaced at the four anchors; 2031 re-interpolated
2030→2032 and 2034 re-interpolated 2033→2035; 2028/2035 boundary anchors
unchanged. option6's headline 10-year moves +$1,172.8B → +$1,164.3B.
option6 is a legacy option kept out of the CRFB-facing dashboard menu;
this is a data-integrity correction to the published CSV/paper artifacts.

## Pooled baseline series (audit M-01)

The static panel shares one current-law baseline series across reforms.
Post-publication splices had broken that: magi100/tax_panel_2005
interpolated baseline columns over their own 18 anchors (a $25.7B spread
against the legacy panel at option6's 2033 anchor), and the new exact
anchors (2029-2033 rescore, the 2062 completion anchor) updated some
reforms' baselines but not the interpolated rows around them.

`scripts/fix_pooled_baseline_series.py` rebuilds the pooled series over
every exact anchor year (2026, 2028-2030, 2032, 2033, 2035…2060, 2062,
2065…2100) and conforms all 1,200 static rows and the
`baseline_aggregates.csv` diagnostics series to it:

- where the June production aggregate measured a year directly, that raw
  value is kept (release invariant: published exact baselines match the
  raw artifact; rescored anchors on byte-identical datasets reproduce
  them to ~$3k);
- the one cross-family disagreement (2029 baseline revenue, $1,368
  spread) resolves to the majority (certinfill) value;
- non-anchor years interpolate the pooled series piecewise-linearly;
  reform-level columns are re-derived as pooled baseline + (linear)
  impact. Impact columns are untouched throughout.

Largest effect: legacy reforms' 2061-2064 rows previously carried a
2060→2065 baseline chord that overshot the measured 2062 baseline by
$41.6B (convex revenue growth); they now carry the exact 2062 value.

## Contract (audit M-03/M-04/M-05)

`results_contract.json` now covers all 2,250 published rows (1,050
behavioral rows included; M-03), computes interpolation parents per
reform and scoring type instead of pooling exact years globally (M-04 —
e.g. option1@2031 cites [2030, 2035], option6@2031 cites [2030, 2032]),
and resolves each exact row's baseline H5 sha from the manifest matching
its run prefix (M-05 — magi100/tax_panel@2035 now cite the certrepro
2035 dataset `088c1f27…` they were actually scored on).

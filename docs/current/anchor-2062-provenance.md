# 2062 exact anchor for option12 and option5 (audit finding H-02)

The 2026-07-22 cross-model audit found that option12's benefit-taxation
phase-out completes in 2062 — from that year its operative tax settings
are identical to option5's — but the published anchor grid (…, 2060,
2065, …) interpolated straight across the kink. The displayed 2062 gap
between the two reforms was $19.5B, shrinking linearly to zero only at
the 2065 anchor. The audit's exact evidence: option12 −$40.4165B vs
option5 −$59.9599B at 2062.

## Dataset

`projected_datasets_certrepro/2062.h5`, built 2026-07-23 in the
certified worktree (`~/PolicyEngine/crfb-cert` @3de8abb6, populace
9f1260b base, `build_v2_projected_datasets.py`), final calibration
exact on the OACT TR2026 pins: OASDI TOB $415.3305B + HI TOB
$347.5620B = $762.8925B (achieved to ~1e-11), payroll $43,719.0B.
Manifest `baseline-manifest-anchor2062.json` (run-id
`crfb-9f1260b-anchor2062`), copied verbatim into
`docs/current/manifests/baseline-dataset-manifest-anchor2062.json` and
registered as a default supplemental manifest of the results contract.

## Cells and gates

Three static cells at 2062 (option1 gate + option12 + option5), run
prefix `anchor2062_20260723`, certified env (policyengine-us 1.700.2),
local worker (`run_v2_local_proof.py`, `require_object_store=False`),
manifest validation fail-closed. Baseline leg computed on the same
dataset (`aggregate_reform_full_h5_results.load_baseline`), cached in
`tmp/anchor2062_baseline.json`. Gates
(`scripts/fix_option12_2062_anchor.py gate`), all passed 2026-07-23:

1. G1 — computed baseline TOB reproduces the OACT pin to six decimals
   (415.330500 / 347.562000 / 762.892500).
2. G2 — option1@2062 = −$762.892500B = −(baseline TOB total) exactly
   (diff 0.000M); the published panel's option1 rows equal
   −baseline_tob_total at every anchor, so this proves env + dataset +
   pairing on the sharpest available identity.
3. G3 — option12@2062 = option5@2062 = −$58.278146B (gap 0.000M),
   confirming the completed phase-out reaches option5's settings.

## Splice

`scripts/fix_option12_2062_anchor.py splice` replaced the option12 and
option5 static rows for 2061–2064 in both results.csv copies in place
(all other rows byte-identical): 2062 becomes the exact anchor
(baseline_source `certrepro_2062_same_dataset_baseline`), 2061
re-interpolates 2060→2062, 2063–2064 re-interpolate 2062→2065.
Headline moves: option12 2062 −$40.42B → −$58.28B; option5 2062
−$59.96B → −$58.28B. From 2062 the two reforms' rows are identical, as
the policies are. Behavioral display rows re-derived for the affected
years (ratio interpolation against the corrected static series; exactly
the 8 option12/option5 2061–2064 rows moved). `results_contract.json`,
`headline_summary.csv`, and the paper's headline exhibit regenerated
(option5 75-year PV −$110.4B → −$109.5B; option12 +$2,600.1B →
+$2,591.4B).

Cell artifacts (scenario.h5 + metadata.json per reform) uploaded to
`r2://axiom-corpus/crfb/reform_full_h5/anchor2062_20260723/…`.

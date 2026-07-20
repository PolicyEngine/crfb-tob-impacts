# Labor-supply substitution-channel fix provenance (2026-07-20)

The behavioral rows published 2026-06-13 through 2026-07-19 (run prefix
`v2pop_tr2026_behavioral_20260612` + `behavioral_endpoint_ratio_interpolation_20260612`)
carried the income channel only. This document records the defect, the fix,
the gates, and the rescore that produced the current rows.

## Defect

`policyengine-core` ≥ 3.24.4 `Simulation.delete_arrays` purged only
`default:`-keyed holder storage, so the `mtr_for_adult_N` sub-branches inside
the named behavioral measurement branches never cleared the parent branch's
cached `household_net_income`; the ancestor walk-up in `Holder.get_array`
served it back as the perturbed value, and both measurement branches recorded
MTR = 1.0 for every simulated adult. `relative_wage_change` was therefore
identically zero and the substitution channel inert. Static/root-simulation
MTRs were unaffected (their stale keys are `default:`-prefixed, which the
purge did clear).

- Upstream report with minimal repro and version bisect:
  [policyengine-us #9086](https://github.com/PolicyEngine/policyengine-us/issues/9086)
- Upstream fix (visibility-chain purge + private per-clone disk views):
  [policyengine-core #521](https://github.com/PolicyEngine/policyengine-core/pull/521),
  released as policyengine-core 3.30.1 on 2026-07-19
- Regression window (empirical bisect, in the issue comments): substitution
  alive and exactly correct through core 3.23.6 (ecosystem-current through
  2026-04-16); core 3.24.0–3.24.3 (2026-04-17) could not load/run
  policyengine-us at all; dead from core 3.24.4 (2026-04-18) through 3.30.0.
  The June 12 production behavioral runs (core 3.26.1) were inside the dead
  window. The v1-era dynamic panel (December 2025, since removed from the
  release surface) predated the window and had a live channel.

## Certified-environment patch

The rescore ran in the certified worktree `~/PolicyEngine/crfb-cert`
(policyengine-us 1.700.2 + policyengine-core 3.26.1) with the
`Simulation.delete_arrays` hunk of #521 backported onto the venv's core.
Patch artifact: `crfb-cert/tmp/lsr_fix/core-3.26.1-delete-arrays-visibility-chain.patch`
(plus `simulation.py.orig` alongside). Disk-side changes from #521 were not
needed: `memory_config` is `None` in these runs, so no `OnDiskStorage` is ever
constructed and the memory-side chain purge is the complete fix. The venv
patch survives until the next `uv sync` in that worktree; re-apply the patch
artifact if the environment is ever re-synced.

## Gates (all passed before rescoring)

1. Single-household repro on the patched venv: measurement MTRs equal the
   static MTRs (0.1965 baseline / 0.2765 reform under a bracket-2 rate
   reform); `relative_wage_change` −0.099564.
2. Static invariance at array level: full-population (160,858 persons)
   `marginal_tax_rate` arrays for the 2026 baseline and static option5 reform
   are bitwise identical with and without the patch.
3. Static invariance at cell level: a full static option5 2026 worker cell on
   the patched venv reproduces the published revenue impact
   (+48.7450417100 $B) to all ten published decimals, and the recomputed 2026
   baseline leg matches the published baseline revenue (2531.9073715394 vs
   2531.9073715400 $B).
4. Baseline-family check: the recomputed 2100 baseline leg on the noclone
   2100 H5 matches the published 2100 baseline (51467.8422854516 vs
   51467.8422855000 $B). An initial attempt against the 9f1260b-family 2100
   H5 (the Modal-volume `crfb-longrun-v2pop-tr2026-9f1260b-20260611` copy,
   now cached at `crfb-tob-impacts/tmp/v2pop_certified_2100/`) produced
   +5.0% and was discarded: the published far-year panel is the noclone
   family. Both endpoint datasets and sidecars SHA-match
   `docs/current/manifests/baseline-dataset-manifest-v2pop-noclone.json`.

## Rescore

- 28 cells: 14 reforms × {2026, 2100}, scoring_type `behavioral`, run prefix
  `lsrfix_behavioral_20260719`, local worker
  (`scripts/run_v2_local_proof.py` → `run_reform_full_h5_cell`,
  `require_object_store=False`), datasets
  `projected_datasets_v2pop/{2026,2100}.h5`, manifest validation fail-closed.
  Runner: `crfb-cert/tmp/lsr_fix/run_behavioral_cells.sh` (two year-lanes,
  resumable, per-cell logs under `crfb-cert/tmp/lsr_fix/logs/`).
- Artifacts: scenario.h5 + metadata.json per cell, uploaded to
  `r2://axiom-corpus/crfb/reform_full_h5/lsrfix_behavioral_20260719/…`
  (upload map: `crfb-cert/tmp/lsr_fix/r2_upload_map.json`); per-cell
  `output_h5_sha256` recorded in the endpoint aggregate.
- Aggregation: `crfb-cert/tmp/lsr_fix/s9_build_endpoint_cells.py` — the same
  `ScenarioAggregate` / `build_reform_result_from_aggregates` path as the
  production aggregator, with baseline legs recomputed on the patched venv
  (`baseline_2026.json`, `baseline_2100.json`) and verified against the
  published rows above. Output replaced
  `results/modal_runs_production/behavioral_endpoint_cells.csv`
  (June file preserved as
  `behavioral_endpoint_cells_broken_20260612_backup.csv`).
- Publication: `scripts/publish_dashboard_results.py` regenerated the
  behavioral exact + ratio-interpolated display rows (new interpolation
  prefix `behavioral_endpoint_ratio_interpolation_20260719`); the published
  static block (1,200 rows including magi100 and tax_panel_2005) was spliced
  through byte-identically — exactly the 1,050 behavioral lines changed in
  `results.csv`. `results_contract.json` regenerated (static-only by design;
  timestamp-only diff).

## Headline effect of the correction

Corrected behavioral revenue impacts move most for the payroll-swap family
(substitution drag: employer contributions become taxable, raising most
earners' MTRs) and flip the behavioral-static ordering for the repeal and
reverse_roth families (their MTR reductions now add work):

| cell | static | income-only (removed) | corrected |
|---|---|---|---|
| option5 2026 | +48.75 | +51.15 | +36.41 |
| option5 2100 | −547.81 | −505.14 | −672.59 |
| option1 2026 | −108.81 | −109.27 | −106.90 |
| option1 2100 | −3319.13 | −3331.70 | −3304.69 |
| reverse_roth 2100 | −1045.76 | −1078.98 | −942.36 |

($B; static and income-only values are the previously published rows.)

Dashboard charts and tables display static scores only, so no displayed
figure changed; the correction affects the downloadable behavioral rows and
the paper's methods description (see the correction note in
`paper/sections/03-methods.qmd`).

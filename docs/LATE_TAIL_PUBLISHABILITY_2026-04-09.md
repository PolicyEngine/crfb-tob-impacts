# Late-Tail Publishability Note

Date: 2026-04-09

## Summary

The standard late-tail static package is not ready for a full `2026-2100` rerun.

We now have two concrete findings for `2075+`:

1. The currently published late-band projected datasets rely on experimental donor-backed composite support augmentation.
2. The non-experimental unaugmented `ss-payroll-tob` path fails the publishability contract at `2075`.
3. The cleaner non-donor augmentation profiles tried so far also fail the same publishability contract by a wide margin.

That means there is not yet a clean production-safe late-tail method for standard `option1-12` results beyond `2074`.

## Why The Current `2075+` Band Is Not Defensible

The current late-band projected H5s were built with donor-backed composite support augmentation. That method is explicitly experimental in the long-term calibration workflow and materially drives the late-year income support.

Local evidence:

- production late-band manifest:
  [calibration_manifest.json](/Users/maxghenis/.codex-worktrees/us-data-clean-rerun/tmp/oact_core_threshold_grid_2075_2100_latesthf/calibration_manifest.json)
- sentinel late-band support reports:
  [support_augmentation_report_2075.json](/Users/maxghenis/.codex-worktrees/us-data-clean-rerun/tmp/oact_core_threshold_grid_sentinel_20260409a_late/support_augmentation_report_2075.json)
- canonical audit log:
  [model_audit_2026-04-08.md](/Users/maxghenis/PolicyEngine/crfb-tob-impacts/results/model_audit_2026-04-08.md)

The late-tail clone households dominate the problematic raw capital-income inputs, so this is not a small presentation or stitching issue.

## Unaugmented `2075` Probe

I ran a cloud-safe one-year publishability probe for:

- year: `2075`
- profile: `ss-payroll-tob`
- target source: `trustees_2025_current_law`
- no donor-backed augmentation

Raw local result:

- [\_tmp_assess_publishable_2075_unaugmented_modal.csv](/Users/maxghenis/PolicyEngine/crfb-tob-impacts/results/_tmp_assess_publishable_2075_unaugmented_modal.csv)

Result:

- `validation_passed = False`
- `calibration_quality = aggregate`
- `effective_sample_size = 26.45` vs required minimum `75`
- `top_10_weight_share_pct = 53.39%` vs allowed maximum `25%`
- `top_100_weight_share_pct = 97.31%` vs allowed maximum `95%`

Important nuance:

- the unaugmented run can hit the aggregate age / SS / payroll / TOB constraints almost exactly
- but it does so with weights that are far too concentrated to satisfy the publishability contract

So the plain non-experimental route is also not good enough for `2075`.

## Candidate Augmentation Probes

I also ran one-year `2075` publishability probes for the cleaner support-augmentation profiles currently exposed by the long-run tooling:

- `late-clone-v1`
- `late-clone-v2`
- `late-composite-v1`
- `late-composite-v2`
- `late-synthetic-grid-v1`
- `late-synthetic-grid-v2`
- `late-mixed-household-v1`

Result:

- none of those profiles came close to the current `ss-payroll-tob` support thresholds
- the best of the set, `late-composite-v1`, still only reached `effective_sample_size = 35.53`
- its `top_10_weight_share_pct = 45.74%`, still far above the allowed `25%`

So the current clean profile family does not rescue `2075+`.

By contrast, the currently published donor-backed composite `2075` dataset does solve the support-concentration side of the contract:

- `effective_sample_size = 161.46`
- `top_10_weight_share_pct = 16.41%`
- `top_100_weight_share_pct = 58.23%`

That isolates the remaining objection more precisely:

- the donor-composite path is the only method we have seen that produces publishable support concentration for `2075`
- but it is still experimental and appears to contaminate late-year capital-income inputs through clone inheritance

So the late-tail problem is no longer "find any method that calibrates." It is "harden the donor-composite method enough that it is defensible."

## Current Decision Boundary

As of this note, the standard package has two options:

1. Treat `2026-2074` as the clean publishable standard static horizon.
2. Approve and validate a new late-tail support method before including `2075-2100`.

What should not happen:

- rerunning `2075-2100` on the current donor-composite regime and treating it as production-clean
- rerunning `2075-2100` unaugmented and pretending the failed publishability metrics are acceptable

## Immediate Next Step

The next work item is not a full rerun. It is method selection for `2075+`.

The cleaner published support profiles have now been checked and do not pass.

So the next concrete work item is to harden and test the donor-composite method itself, especially by neutralizing non-target capital-income inheritance on clone rows, before any new full standard static rerun.

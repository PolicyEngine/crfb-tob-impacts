# Late-Tail Publishability Note

Date: 2026-04-09

## Summary

The standard late-tail static package is not ready for a full `2026-2100` rerun.

We now have two concrete findings for `2075+`:

1. The currently published late-band projected datasets rely on experimental donor-backed composite support augmentation.
2. The non-experimental unaugmented `ss-payroll-tob` path fails the publishability contract at `2075`.

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

## Current Decision Boundary

As of this note, the standard package has two options:

1. Treat `2026-2074` as the clean publishable standard static horizon.
2. Approve and validate a new late-tail support method before including `2075-2100`.

What should not happen:

- rerunning `2075-2100` on the current donor-composite regime and treating it as production-clean
- rerunning `2075-2100` unaugmented and pretending the failed publishability metrics are acceptable

## Immediate Next Step

The next work item is not a full rerun. It is method selection for `2075+`.

That means evaluating candidate late-tail support approaches against the existing publishability contract, then explicitly choosing one before any new full standard static rerun.

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

## 2026-04-10 Panel Review Update

The subagent review panel reaffirmed a no-go for a full `2026-2100` series until the late-tail sentinel panel passes.

New confirmed blocker:

- the donor-composite role-candidate layer was solving against taxable payroll but handing uncapped clone payroll into target-year calibration blueprints
- under `policyengine-us==1.634.4`, a 2075 diagnostic showed 65 selected role-composite candidates above cap
- weighted uncapped payroll was about `$76.56T` while weighted taxable payroll was about `$72.13T`
- the resulting `5.78%` uncapped-vs-taxable gap is large enough to explain the observed `2075` payroll miss under strict `0.5%` thresholds

Forward fix under test:

- role-donor composite wage allocation now preserves cap-aware taxable payroll
- clone reports now record `target_taxable_payroll_total`
- calibration blueprints and clone-translation diagnostics prefer taxable payroll targets when present
- a 2075 candidate-level diagnostic now shows zero over-cap selected candidates and weighted taxable payroll matching the Trustees payroll target

This narrows the next validation step to one persisted `2075` sanitized donor-composite sentinel under the clean strict-threshold worktree. If that passes, expand to the bounded sentinel panel before any full static run.

## 2026-04-10 Persisted 2075 Sentinel

The persisted sanitized donor-composite `2075` sentinel was rerun from `policyengine-us-data` commit `d43181b1` with:

- `policyengine-us==1.634.4`
- Social Security payroll cap path: `2035=$254,400`, `2075=$969,300`, `2100=$2,235,900`
- `target_source=trustees_2025_current_law`
- `tax_assumption=trustees-core-thresholds-v1`
- `support_augmentation_profile=donor-backed-composite-v1`
- `support_augmentation_sanitize_worker_non_target_income=true`

Calibration result:

- `validation_passed=true`
- `calibration_quality=exact`
- validation issues: none
- Social Security, payroll, OASDI TOB, and HI TOB targets all hit to displayed precision
- support ESS about `214.5`
- top-10 weight share about `13.3%`
- top-100 weight share about `55.3%`
- positive household count `41,634`

Remaining blocker:

- clone non-target income still dominates several capital-income fields even after worker-row sanitization
- clone shares are still about `99.6%-99.9%` for taxable interest, qualified dividends, non-qualified dividends, long-term gains before response, estate income, and rental income
- baseline income tax printed at about `$1,516.6T`, which is a red flag for total-revenue interpretation even though TOB calibration now passes

Decision:

- The payroll/calibration blocker is fixed for the 2075 sentinel.
- The full `2026-2100` static run is still not cleared until the clone-income dominance is either explicitly accepted/documented or addressed with broader clone non-target-income handling.

## 2026-04-10 All-Clone Gross-Income Sanitizer Sentinel

The donor-composite sanitizer was widened from worker-only investment/retirement income to all donor-clone non-target IRS gross-income sources. The widened list keeps target earnings and Social Security intact, but zeros clone-inherited capital, pension/retirement, pass-through, farm, unemployment, miscellaneous, and similar non-target AGI sources.

Validated commits in `policyengine-us-data`:

- `48b5259c`: add opt-in all-clone non-target-income sanitizer
- `9b89c43a`: record explicit `non_target_income_sanitizer_mode`
- `01efa47f`: include all non-target gross-income sources in the sanitizer

Focused local validation:

- `uv run ruff check ...`: passed
- `uv run pytest tests/unit/test_long_term_calibration_contract.py -q`: `54 passed`

Persisted `2075` Modal sentinel on commit `01efa47f`:

- `target_source=trustees_2025_current_law`
- `tax_assumption=trustees-core-thresholds-v1`
- `policyengine-us==1.634.4`
- Social Security payroll cap path: `2035=$254,400`, `2075=$969,300`, `2100=$2,235,900`
- support augmentation: `donor-backed-composite-v1`, run-year aligned
- sanitizer mode: `clone_all`

Result:

- calibration passes exactly
- validation issues: none
- Social Security, taxable payroll, OASDI TOB, and HI TOB all hit to displayed precision
- negative weights: zero
- support ESS: about `206.7`
- top-10 weight share: about `14.6%`
- top-100 weight share: about `54.2%`
- positive households: `41,634`
- tracked clone non-target income contribution: zero for all measured variables
- printed income tax falls from about `$1,516.6T` under worker-only sanitization and `$626.6T` under partial all-clone sanitization to about `$15.35T`
- income-tax-to-Trustees-taxable-payroll ratio falls to about `0.213`

Interpretation:

- The 2075 calibration/support/revenue sentinel now looks mechanically publishable under the widened all-clone sanitizer.
- This does not clear the full series. It clears the next step: run the bounded sentinel matrix across the known splice/outlier years before any full static rerun.

Remaining full-run blockers:

- CRFB full-run wrapper/defaults have been switched from `oact_2025_08_05_provisional` to `trustees_2025_current_law`, but the new wrapper path still needs a bounded sentinel matrix before use.
- The dirty local tolerance relaxation in `policyengine-us-data` must not be used.
- The production `policyengine-us` checkout must include the indefinite `non_refundable_ss_credit`, 2100-safe senior deduction endpoint, and Trustees economic-uprating path.
- Dynamic remains separately blocked until the active `policyengine-us` checkout implements age-based labor-supply elasticities.

## 2026-04-10 PE-US Integration Update

A clean `policyengine-us` integration worktree was created at `/Users/maxghenis/.codex-worktrees/us-crfb-integration` on branch `codex/crfb-integrated-assumptions`.

Integrated assumptions:

- current `upstream/main` / package baseline at `policyengine-us==1.634.4`
- Trustees uprating branch (`upstream/uprating`) merged for long-run SSA NAWI and SSA uprating inputs
- indefinite CRFB `non_refundable_ss_credit` via commit `eb924e3d6d`
- CRFB senior deduction extension made indefinite beyond `2099`
- age-based labor-supply elasticity branch merged for dynamic runs

Validation:

- `uv run ruff check ...`: passed for touched PE-US reform, TOB-revenue, and labor-supply files
- PE-US Python unit subset passed: `27 passed`
- Lightweight integration smoke passed:
  - `ss_credit` remains in non-refundable credits in `2100`
  - `additional_senior_deduction` remains in both itemizing and non-itemizing deduction lists in `2100`
  - SSA long-run inputs are active at `2100`
  - age-based income and substitution elasticities double at age `65`

Important merge finding:

- The initial `-X theirs` merge of `upstream/uprating` partially spliced the older proportional TOB allocation code into current main's newer double-branch TOB files.
- That created undefined names in `tob_revenue_oasdi` and `tob_revenue_medicare_hi`.
- The integration branch now restores current main's double-branch formulas and updates the branch-added unit tests to match current behavior.
- A second dynamic-only seam was fixed: `labor_supply_behavioral_response` still treated `elasticities.income` as a scalar even after the age-based branch changed it into a parameter node. The guard now checks `income.all`, `income.base`, and all substitution components explicitly.

Current long-run cap path from the integration checkout:

- `2035=$254,400`
- `2075=$1,030,411`
- `2100=$2,469,329`

This differs from the prior `policyengine-us==1.634.4` package-only sentinel cap path because the integration checkout now includes Trustees NAWI/uprating inputs from the unmerged uprating branch.

Attempted local 2075 H5 sentinel:

- command used strict validation, `target_source=trustees_2025_current_law`, `tax_assumption=trustees-core-thresholds-v1`, `donor-backed-composite-v1`, run-year alignment, and all-clone non-target-income sanitization
- the process was CPU-active but still had not written `2075.h5` after about `30` minutes
- RSS climbed to about `18.2GB`
- the process was terminated intentionally to avoid another local desktop memory blow-up

Decision:

- The PE-US integration branch is ready for remote/constrained sentinel execution.
- The local desktop is not a safe gate for full late-year H5 generation under the integrated Trustees path.
- Next gate should run the bounded sentinel matrix remotely or with an explicit memory cap before any full static run.

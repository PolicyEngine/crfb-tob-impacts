# Special-Case Rerun Notes

## 2026-04-11 11:50 EDT

### Scope

- Objective: rerun `option13` and `option14_stacked` on the same clean exact Trustees 2025 current-law projected dataset lineage used for the rebuilt standard static series.
- Projected dataset snapshot:
  `/Users/maxghenis/PolicyEngine/crfb-tob-impacts/projected_datasets_snapshots/trustees-special-cases-2035-2100-current_20260411`
- PE-US checkout:
  `/Users/maxghenis/.codex-worktrees/us-crfb-integration`

### Runner fixes applied

- `batch/run_option13_modal.py`
  - image build now copies local dirs with `copy=True` so Modal does not reject later build steps
  - mounted snapshot path now sets both `CRFB_PROJECTED_DATASETS_SNAPSHOT_PATH` and `CRFB_PROJECTED_DATASETS_PATH`
  - output prefixes are now explicit function arguments rather than implicit remote env assumptions
  - added a submit-only path that records spawned call IDs to a local manifest
- targeted test coverage extended in `tests/test_option13_special_cases.py`

### Smoke validation

- Smoke run years: `2035`, `2100`
- Result: clean completion for both `option13` and `option14`
- `2100` balanced-fix endpoint no longer shows the old negative-HI-rate pathology
- Clean `2100 option13` values observed from the written row:
  - `benefit_multiplier = 0.8865218701714921`
  - `new_employee_hi_rate = 0.0128643003205098`
  - `new_employer_hi_rate = 0.0128643003205098`
  - `ss_rate_increase_pp = 2.395638807222844`
  - `hi_rate_increase_pp = -0.327139935898022`

### Full rerun recovery status

- Detached full run app:
  `ap-tIe4zAyO65hgaVSlEqDxZ8`
- The app eventually stopped after writing recoverable outputs to the Modal
  volume.
- Submission-manifest run:
  `results/special_case_submissions/option13-14-exact-2035-2100-20260411.json`
  - contains 66 spawned call IDs under output prefix
    `special_case_reruns/option13-14-exact-2035-2100-20260411`
  - immediate `FunctionCall.from_id(...).get()` checks returned terminated/remote-error status, so this spawn-only path should not be treated as the authoritative live run until proven otherwise
- Recovered volume output:
  `results/recovered_special_case_runs/special_case_reruns__option13-14-exact-2035-2100-20260411`
  - `option13`: 66 year files recovered for `2035-2100`
  - `option14`: 66 year files recovered for `2035-2100`
  - recovery required a fix in `src/modal_run_recover.py` because `modal volume get`
    flattened the requested prefix one level deeper than the helper assumed
  - some container logs ended with `Runner has been shutting down for too long`,
    but the recovered artifact set is complete, so the rerun should be treated as
    successful at the publication-artifact level

### Interpretation

- Standard static `option1-12` remain the clean finished static series.
- `option13/14` are now fully rerun and recovered on the clean lineage.
- The static 14-option delivery can now be treated as one unified Trustees-lineage
  package rather than a clean standard block plus patched special-case endpoints.

# Long-Run Rescoring Findings

This note summarizes what we have established so far from rescoring reforms on
corrected long-run saved H5 datasets instead of relying on the legacy
baseline-override CSV workflow.

## Setup

Current corrected long-run checks use:

- calibrated saved H5 datasets from the `us-data-calibration-contract` worktree
- target source `oact_2025_08_05_provisional`
- baseline tax assumption `trustees-core-thresholds-v1`
- the local `policyengine-us` wage-base fix from PR `#7912`

Representative saved H5 inputs used so far:

- `2075.h5`
- `2090.h5`
- `2100.h5`

## Main Findings

1. `results/oact_static_current.csv` is stale for long-run reform scoring.

   It is not equivalent to rescoring reforms on corrected long-run microdata.
   The corrected saved-H5 path changes actual reform impacts, not just baseline
   TOB columns.

2. The corrected long-run baseline changes reform scores materially.

   Three-year spot checks on `option1`, `option8`, and `option11` show that the
   deltas versus the old CRFB file are often large enough to matter for any
   external reporting.

3. The sign of the change is not uniform across reforms.

   Repeal (`option1`) becomes less negative once corrected baseline TOB is
   lower, but non-repeal reforms can move either up or down depending on year
   and trust-fund component.

4. The saved-H5 rescoring workflow is operationally usable now.

   It is still expensive on first load for a new long-run year, but baseline
   caching makes repeated checks on the same year practical.

5. Full far-tail all-reforms runs are now complete for `2090` and `2100`.

   Those results are tracked separately in
   `analysis/saved_h5_all_reforms_2090_2100.md`.

6. Not every long-run duplicate row should be read as true policy convergence.

   - `option5`, `option6`, and `option12` do appear to converge to the same
     long-run policy state.
   - But the current `policyengine-us` dependency also introduces two
     implementation caveats:
     - the Social Security credit path appears to stop affecting liability
       after `2035`, which affects the interpretation of `option4` and
       `option11`
     - the active senior-deduction extension stops at `2099-12-31`, so `2100`
       `option3` results are not a clean permanent-policy endpoint

## Representative Deltas

All values below are in billions of dollars.

| Reform | Year | New Revenue | Old Revenue | Delta | OASDI TOB Delta | HI TOB Delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `option1` | 2075 | -1476.389 | -1500.710 | 24.321 | 12.790 | 11.532 |
| `option8` | 2075 | 413.597 | 510.380 | -96.783 | -16.263 | -80.529 |
| `option11` | 2075 | 79.129 | 105.036 | -25.906 | 1.933 | -27.839 |
| `option1` | 2090 | -2634.736 | -2646.220 | 11.484 | 3.974 | 7.510 |
| `option8` | 2090 | 922.182 | 859.300 | 62.882 | -31.711 | 94.594 |
| `option11` | 2090 | 297.056 | 181.358 | 115.698 | -18.457 | 134.155 |
| `option1` | 2100 | -3841.095 | -3852.810 | 11.715 | 7.356 | 4.359 |
| `option8` | 2100 | 855.222 | 1318.330 | -463.108 | -44.394 | -418.714 |
| `option11` | 2100 | 49.579 | 321.851 | -272.272 | -33.532 | -238.740 |

## Runtime Notes

- First baseline load for a new long-run year is expensive, roughly four
  minutes in the current environment.
- Once cached, later rescoring on the same saved H5 skips that baseline pass.
- Per-reform scoring is still expensive enough that full-year all-reforms runs
  should be treated as batch jobs, not interactive checks.

## Recommended Year Grid For Fast Delivery

If the goal is to produce an updated set of CRFB numbers quickly, the most
defensible coarse year grid is:

- every year `2026-2035`
- plus `2036`, `2037`, `2038`, `2045`, `2049`, `2062`, `2063`
- plus `2070`, `2080`, `2090`, `2100`

This grid is based on actual reform discontinuities in `src/reforms.py`, not
just arbitrary decade spacing.

## Current Caveat

These rescoring results still depend on the local `policyengine-us` wage-base
fix from PR `#7912`, which is not merged yet. Until that fix lands, the
workflow is reproducible from branch state, not from released package state.

# Saved-H5 Three-Year Checks

These local checks compare reform scores from corrected long-run saved H5 datasets
against the current `results/oact_static_current.csv` baseline-override outputs.

Method:
- Baseline datasets come from the `us-data-calibration-contract` worktree using
  target source `oact_2025_08_05_provisional`.
- Baseline scoring composes the `trustees-core-thresholds-v1` tax-assumption
  reform from `policyengine_us_data/datasets/cps/long_term/tax_assumptions.py`.
- Runs currently depend on the local `policyengine-us` wage-base fix from PR
  `#7912`.

Three-year spot checks:

| Reform | Year | Revenue Impact New ($B) | Revenue Impact Old ($B) | Delta ($B) | OASDI TOB Delta ($B) | HI TOB Delta ($B) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `option1` | 2075 | -1476.389 | -1500.710 | 24.321 | 12.790 | 11.532 |
| `option8` | 2075 | 413.597 | 510.380 | -96.783 | -16.263 | -80.529 |
| `option11` | 2075 | 79.129 | 105.036 | -25.906 | 1.933 | -27.839 |
| `option1` | 2090 | -2634.736 | -2646.220 | 11.484 | 3.974 | 7.510 |
| `option8` | 2090 | 922.182 | 859.300 | 62.882 | -31.711 | 94.594 |
| `option11` | 2090 | 297.056 | 181.358 | 115.698 | -18.457 | 134.155 |
| `option1` | 2100 | -3841.095 | -3852.810 | 11.715 | 7.356 | 4.359 |
| `option11` | 2100 | 49.579 | 321.851 | -272.272 | -33.532 | -238.740 |
| `option8` | 2100 | 855.222 | 1318.330 | -463.108 | -44.394 | -418.714 |

Interpretation:
- The corrected long-run baseline changes actual reform scores, not just baseline
  TOB columns.
- Repeal (`option1`) becomes less negative once corrected baseline TOB is lower.
- Non-repeal options can also move materially, but the sign and magnitude are
  not uniform across reforms or years.

Caveats:
- These are still spot checks, not a full rerun across all reforms and years.
- The saved-H5 rescoring path is now usable for repeated year-level checks, but
  the first baseline load for a new year is still expensive; the baseline cache
  in `.cache/saved_h5_baselines/` is intended to amortize that cost.

Source artifacts:
- `results/local_oact_saved_h5_3year_checks.csv`
- `results/local_oact_saved_h5_3year_checks_billions.csv`

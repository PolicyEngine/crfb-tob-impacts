# Saved-H5 All-Reforms Checks For 2090 And 2100

These tables summarize the completed all-reforms rescoring runs on corrected
long-run saved H5 datasets for `2090` and `2100`.

Setup:

- target source: `oact_2025_08_05_provisional`
- baseline tax assumption: `trustees-core-thresholds-v1`
- scoring path: `scripts/score_saved_h5_reforms.py`
- comparison file: `results/oact_static_current.csv`
- current dependency: local `policyengine-us` wage-base fix from PR `#7912`

All values below are in billions of dollars.

## 2090

| Reform | Revenue New | Revenue Old | Revenue Delta | OASDI TOB Delta | HI TOB Delta |
| --- | ---: | ---: | ---: | ---: | ---: |
| `option1` | -2634.736 | -2646.220 | 11.484 | 3.974 | 7.510 |
| `option2` | 297.056 | 205.390 | 91.666 | -31.711 | 123.367 |
| `option3` | 296.578 | 191.990 | 104.588 | -32.697 | 127.299 |
| `option4` | 297.056 | 121.805 | 175.251 | 34.372 | 140.878 |
| `option5` | -607.642 | 429.440 | -1037.082 | 3.974 | 7.510 |
| `option6` | -607.642 | 429.440 | -1037.082 | 3.974 | 7.510 |
| `option7` | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| `option8` | 922.182 | 859.300 | 62.882 | -31.711 | 94.594 |
| `option9` | 521.135 | 420.638 | 100.497 | -31.707 | 132.204 |
| `option10` | 725.488 | 639.136 | 86.352 | -31.707 | 118.059 |
| `option11` | 297.056 | 181.358 | 115.698 | -18.457 | 134.155 |
| `option12` | -607.642 | 429.440 | -1037.082 | 3.974 | 7.510 |

## 2100

| Reform | Revenue New | Revenue Old | Revenue Delta | OASDI TOB Delta | HI TOB Delta |
| --- | ---: | ---: | ---: | ---: | ---: |
| `option1` | -3841.095 | -3852.810 | 11.715 | 7.356 | 4.359 |
| `option2` | 49.579 | 340.350 | -290.771 | -44.394 | -246.377 |
| `option3` | 49.579 | 340.350 | -290.771 | -44.394 | -246.377 |
| `option4` | 49.579 | 245.619 | -196.040 | 33.303 | -229.343 |
| `option5` | -835.344 | 865.640 | -1700.984 | 7.356 | 4.359 |
| `option6` | -835.344 | 865.640 | -1700.984 | 7.356 | 4.359 |
| `option7` | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| `option8` | 855.222 | 1318.330 | -463.108 | -44.394 | -418.714 |
| `option9` | 316.792 | 663.480 | -346.687 | -44.396 | -302.291 |
| `option10` | 585.824 | 990.900 | -405.076 | -44.396 | -360.679 |
| `option11` | 49.579 | 321.851 | -272.272 | -33.532 | -238.740 |
| `option12` | -835.344 | 865.640 | -1700.984 | 7.356 | 4.359 |

## High-Level Read

- The corrected long-run baseline materially changes almost every non-zero
  reform effect at both `2090` and `2100`.
- The direction is not uniform across reforms.
  - `option1` becomes modestly less negative in both years.
  - several positive-revenue options shrink sharply by `2100`.
  - some `2090` non-repeal options become larger than the old file implied.
- Several reforms collapse to identical results in the corrected path, but
  those matches do not all mean the same thing.
  - `option5`, `option6`, and `option12` match exactly in both `2090` and
    `2100`, which is consistent with those policies reaching the same long-run
    end state.
  - `option2`, `option4`, and `option11` clustering by `2090` and `2100`
    should not yet be interpreted as clean economic convergence. Under the
    current `policyengine-us` dependency, the Social Security credit path
    appears to stop affecting liability after `2035`, so these matches are at
    least partly an implementation caveat.
  - `option2` and `option3` match in `2100`, but the active senior-deduction
    extension in `policyengine-us` stops at `2099-12-31`, so the `2100`
    equality is not a clean permanent-policy endpoint.
- `option7` remains exactly zero in both the old and corrected paths.

## Source Artifacts

The local result CSVs used for these tables are:

- `results/local_oact_saved_h5_2090_all_reforms.csv`
- `results/local_oact_saved_h5_2100_all_reforms.csv`

These CSVs are local runtime outputs under `results/` and are not tracked in
git; this markdown file is the tracked summary.

## Full-H5 selected-panel static results

The May 22 full-H5 production run completed all `276` exact selected standard-option cells: `12` reforms by `23` years (`2026-2035` annually and every fifth year from `2040` through `2100`). Exact completed cells have durable R2 `scenario.h5`, `metadata.json`, and `complete.json` markers. Aggregation is downstream from those H5s and is labeled by row in the public CSV.

Dashboard-facing standard-option rows use the exact full-H5 microsimulation result in modeled years. The `624` non-modeled static annual rows after `2035` are linearly interpolated only so charts and 75-year totals remain continuous. The public results surface is `results.csv`, with `scoring_type` distinguishing static from labor-supply response rows. No reference baseline substitution, display normalization, or post-hoc TOB calibration is applied in `results.csv`.

### Ten-year static revenue impacts

| Reform | 2026-2035 revenue impact ($B) |
| --- | --- |
| option1 | -1,905.5 |
| option7 | +55.7 |
| option3 | +81.7 |
| option4 | +113.0 |
| option11 | +161.1 |
| option5 | +214.1 |
| option2 | +244.4 |
| option9 | +398.0 |
| option10 | +553.0 |
| option8 | +709.5 |
| option6 | +1,114.5 |
| option12 | +1,937.6 |

### Milestone static revenue impacts

| Reform | 2035 | 2050 | 2075 | 2100 |
| --- | --- | --- | --- | --- |
| option1 | -257.9 | -507.5 | -1,503.5 | -3,863.5 |
| option2 | +27.1 | +44.1 | +121.5 | +366.7 |
| option4 | +5.4 | +22.8 | +102.7 | +346.9 |
| option5 | +1.5 | -52.6 | -324.5 | -1,401.5 |
| option8 | +87.7 | +155.3 | +470.0 | +1,275.9 |
| option10 | +67.4 | +118.1 | +352.7 | +961.8 |
| option12 | +203.7 | +97.9 | -324.5 | -1,401.5 |

### Current baseline diagnostics

Baseline income tax is intentionally shown as the direct full-H5 microsimulation aggregate, not normalized to an external revenue baseline. That raw series is visibly high: it peaks at `251.1%` of GDP in `2045`. The TOB baseline is much smoother: total TOB is `3,863.5B` in `2100`, or `2.06%` of OASDI taxable payroll. The generated post-OBBBA TOB target remains a diagnostic comparison only; current gaps are exposed in `baseline_aggregates.csv`.

### Late-horizon Roth-family note

The structural employer-payroll swap family (`option5`, `option6`, and `option12`) worsens materially from `2095` to `2100` in the exact static full-H5 rows. For `option12`, the static revenue impact moves from `-597.4B` in `2095` to `-1,401.5B` in `2100`. This is not an interpolation artifact; both years are exact selected-year H5 outputs and should remain a release caveat until the late-horizon baseline/provenance issues are fully closed.

## Behavioral endpoint results

The current behavioral endpoint run `full_h5_v2pop_tr2026_behavioral_endpoints_20260612` completed all `28` endpoint cells: `2026` and `2100` for all fourteen current reform rows. Each endpoint cell saved durable R2 `scenario.h5`, `metadata.json`, and `complete.json` artifacts before aggregation. The `1,022` non-endpoint behavioral display rows use documented linear interpolation of behavioral/static ratios between those exact endpoints.

The public combined `results.csv` keeps static and behavioral rows in one file and distinguishes them with `scoring_type`. Behavioral endpoint rows use the current v2 populace/TR2026 baseline H5s; non-endpoint behavioral rows are derived only from the documented endpoint-ratio interpolation.

### Ten-year behavioral revenue impacts

| Reform | 2026-2035 revenue impact ($B) |
| --- | --- |
| option1 | -1,918.4 |
| option7 | +56.1 |
| option3 | +81.8 |
| option4 | +113.3 |
| option11 | +161.7 |
| option5 | +225.0 |
| option2 | +244.7 |
| option9 | +399.2 |
| option10 | +555.1 |
| option8 | +712.5 |
| option6 | +1,130.4 |
| option12 | +1,967.9 |

### 2100 behavioral vs static revenue impacts

| Reform | Static ($B) | Behavioral ($B) | Difference ($B) |
| --- | --- | --- | --- |
| option1 | -3,863.5 | -3,892.9 | -29.4 |
| option7 | -0.0 | -0.0 | +0.0 |
| option4 | +346.9 | +347.1 | +0.2 |
| option2 | +366.7 | +367.1 | +0.4 |
| option3 | +366.7 | +367.1 | +0.4 |
| option11 | +366.7 | +367.1 | +0.4 |
| option9 | +657.9 | +660.7 | +2.8 |
| option10 | +961.8 | +967.2 | +5.3 |
| option8 | +1,275.9 | +1,283.8 | +7.9 |
| option5 | -1,401.5 | -1,378.3 | +23.2 |
| option6 | -1,401.5 | -1,378.3 | +23.2 |
| option12 | -1,401.5 | -1,378.3 | +23.2 |

The largest endpoint behavioral movement versus static is `option1` in `2100` at `-29.4B`; the employer-payroll swap family (`option5`, `option6`, `option12`) moves by about `+23.2B` in `2100`. The corrected `option7` `2100` endpoint is effectively zero, confirming the previous common late-year labor-response drag was an artifact of the wrong behavioral baseline branch.

### Cost estimate

Fresh cost reporting should come from the Modal usage page for the current v2 populace/TR2026 apps. The dashboard release artifacts no longer carry the stale May 2026 cost estimate.

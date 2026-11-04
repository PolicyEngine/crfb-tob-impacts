We also score labor-supply responses for thirteen of the
fifteen reforms (all but `magi100` and `tax_panel_2005`) and
for the `option6` sensitivity case. For each, we simulate full reform H5 files
at `2026` and `2100`, plus `2062` for `option5` and `option12` and `2033` for `option6`, and
derive aggregates from those files with PolicyEngine's MicroSeries operations.
Between anchors, we interpolate each metric's ratio of behavioral to static
results linearly and apply it to the static annual row; where the static result
changes sign within a segment, we interpolate the behavioral values directly.
The rows appear in the public results file under `scoring_type = behavioral`
and carry both the income and substitution channels. We treat static scoring as
primary: the labor-supply results give partial-equilibrium estimates under the
age-based elasticity schedule in @sec-labor-supply, not official CBO or JCT
scores.

The table reports each reform's revenue impact with labor-supply responses at
the two endpoints, and the response effect, which subtracts the static impact.

| Reform | 2026 revenue impact ($B) | 2026 response effect ($B) | 2100 revenue impact ($B) | 2100 response effect ($B) |
| --- | --- | --- | --- | --- |
| option1 | -106.9 | +1.9 | -3,304.7 | +14.4 |
| option2 | +26.6 | +0.0 | +233.4 | +2.1 |
| option3 | +26.6 | +0.0 | +233.4 | +2.1 |
| option4 | +30.5 | -0.3 | +189.0 | +2.0 |
| option5 | +36.4 | -12.3 | -672.6 | -124.8 |
| option6 (sensitivity) | +17.6 | -2.8 | -672.6 | -124.8 |
| option7 | +16.5 | -0.2 | +0.0 | +0.0 |
| option8 | +59.5 | -0.6 | +1,028.8 | +2.2 |
| option9 | +37.4 | -0.2 | +496.4 | +3.1 |
| option10 | +48.3 | -0.4 | +762.7 | +3.6 |
| option11 | +30.4 | -0.4 | +233.4 | +2.1 |
| option12 | +143.5 | -15.8 | -672.6 | -124.8 |
| reverse_roth | -46.9 | +10.7 | -942.4 | +103.4 |
| tax93 | +43.9 | -0.3 | +656.4 | +3.9 |

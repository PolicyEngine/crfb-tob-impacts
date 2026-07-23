The static panel covers `16` reforms with `290` exact full-H5
anchor cells; every non-anchor annual row is display interpolation between
those exact outputs, labeled per row in the public CSV. Labor-supply response
scoring is supplemental: exact endpoint cells at `2026` and `2100` for the
fourteen contract-standard reforms, with intermediate years interpolated from
endpoint ratios. All exact cells carry durable artifact lineage
(`run_prefix`, output-H5 SHA-256) recorded per row.

### Milestone static revenue impacts

| Reform | 2035 | 2050 | 2075 | 2100 |
| --- | --- | --- | --- | --- |
| magi100 | +25.7 | +36.2 | +88.3 | +217.4 |
| option1 | -223.5 | -442.2 | -1,334.0 | -3,319.1 |
| option10 | +89.3 | +129.3 | +320.7 | +759.1 |
| option11 | +22.9 | +32.7 | +103.4 | +231.3 |
| option12 | +215.0 | +150.8 | -218.0 | -547.8 |
| option2 | +48.9 | +54.2 | +103.4 | +231.3 |
| option3 | +14.5 | +27.0 | +98.5 | +231.3 |
| option4 | +17.5 | +19.4 | +61.3 | +187.1 |
| option5 | +39.3 | +17.2 | -218.0 | -547.8 |
| option6 | +164.5 | +17.2 | -218.0 | -547.8 |
| option7 | +0.0 | +0.0 | +0.0 | +0.0 |
| option8 | +110.0 | +168.1 | +431.0 | +1,026.6 |
| option9 | +69.0 | +91.4 | +211.8 | +493.3 |
| reverse_roth | -83.5 | -171.9 | -403.3 | -1,045.8 |
| tax93 | +81.1 | +114.0 | +276.8 | +652.5 |
| tax_panel_2005 | -6.7 | -24.7 | -75.6 | -141.1 |

### Behavioral endpoints versus static

| Reform | 2026 behavioral, (minus static) ($B) | 2100 behavioral, (minus static) ($B) |
| --- | --- | --- |
| option1 | -106.9 (+1.9) | -3,304.7 (+14.4) |
| option10 | +48.3 (-0.4) | +762.7 (+3.6) |
| option11 | +30.4 (-0.4) | +233.4 (+2.1) |
| option12 | +143.5 (-15.8) | -672.6 (-124.8) |
| option2 | +26.6 (+0.0) | +233.4 (+2.1) |
| option3 | +26.6 (+0.0) | +233.4 (+2.1) |
| option4 | +30.5 (-0.3) | +189.0 (+2.0) |
| option5 | +36.4 (-12.3) | -672.6 (-124.8) |
| option6 | +17.6 (-2.8) | -672.6 (-124.8) |
| option7 | +16.5 (-0.2) | +0.0 (+0.0) |
| option8 | +59.5 (-0.6) | +1,028.8 (+2.2) |
| option9 | +37.4 (-0.2) | +496.4 (+3.1) |
| reverse_roth | -46.9 (+10.7) | -942.4 (+103.4) |
| tax93 | +43.9 (-0.3) | +656.4 (+3.9) |

Labor-supply response results carry both the income and substitution
channels and are partial-equilibrium estimates under the project's age-based
elasticity schedule, not official CBO or JCT scores.

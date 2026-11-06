# Late-Year Support Gates

Late-year datasets are publication-eligible only when the calibration metadata
passes both aggregate household-support checks and policy-target contributor
checks. The runtime starts applying these gates in `2075` by default through
`CRFB_SUPPORT_GATE_START_YEAR`.

## Why This Is Not One ESS Rule

The previous draft gate used `1,000` as a single minimum effective sample size
for every late-year artifact. That would reject historically stable exact
datasets: the stable `2034` and `2035` H5s reviewed in
[#115](https://github.com/PolicyEngine/crfb-tob-impacts/issues/115) had total
effective sample sizes around `800` with low concentration.

The failure mode we need to catch is more specific. Unstable late-year
artifacts can have acceptable total household support while the households that
actually contribute to OASDI or HI taxation of benefits are sparse and
concentrated. Those artifacts should fail on TOB-contributor support, not on a
blunt total-ESS rule.

## Aggregate Household Gates

| Metric | Default publication gate |
| --- | ---: |
| Positive-weight household count | at least `1,000` |
| Total effective sample size | at least `300` |
| Top-10 household weight share | at most `15%` |
| Top-100 household weight share | at most `45%` |

Profile metadata can set stricter aggregate gates. Environment overrides cannot
weaken these hard stops unless `CRFB_ALLOW_UNSAFE_LONG_RUN_ARTIFACT=1` is set,
which is for non-publishable diagnostics only.

## Policy-Target Contributor Gates

| Target | Positive contributors | Contributor ESS | Top-10 share | Top-100 share | Max share |
| --- | ---: | ---: | ---: | ---: | ---: |
| Social Security income | `1,000` | `25` | `60%` | `95%` | `15%` |
| Payroll tax base | `1,000` | `200` | `20%` | `50%` | `5%` |
| OASDI taxation of benefits | `1,000` | `50` | `50%` | `95%` | `15%` |
| HI taxation of benefits | `1,000` | `50` | `50%` | `95%` | `15%` |

The TOB gates are the operative guardrails for late-year reform scores. A
dataset can pass aggregate household support but still be rejected if the OASDI
or HI taxation-of-benefits contributors are too sparse or concentrated.
The max-share gate is intentionally less restrictive than the top-10 and
top-100 checks: it catches single-record domination without rejecting exact
late-year artifacts where a broad contributor pool is stable but the largest
taxable-benefits contributor is still just over `10%`.

## Published baselines

The commits that built the published baselines (`3de8abb6` and `c5e4f1a6`, which
each manifest's `source_sha` names) applied the limits above, with contributor
gates from `2075`. `src/projection.py` at head applies contributor gates in every
year, with a floor of `35` on the two taxation-of-benefits effective sample sizes.
All 21 published anchor years clear the limits above in every year, and
`tests/test_paper_text.py` checks that against `run-provenance.json`.

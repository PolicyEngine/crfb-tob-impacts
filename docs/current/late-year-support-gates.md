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

## Donor-Augmentation Gates

Production delivery should not rely on donor-backed approximate artifacts, but
the runtime still validates any dataset carrying
`donor-backed-composite-v1` metadata. The donor gates are intentionally
separate from the aggregate household gates because donor pools are smaller by
construction.

| Donor metric | Default publication gate |
| --- | ---: |
| Donor-family ESS | at least `300` |
| Top-10 donor-family weight share | at most `15%` |
| Max donor-family weight share | at most `10%` |
| Positive clone donor-family count | at least `300` |
| Clone donor-family ESS | at least `10` |
| Top-10 clone donor-family weight share | at most `85%` |
| Top-100 clone donor-family weight share | at most `98%` |
| Max clone donor-family weight share | at most `20%` |
| Positive older-donor clone count | at least `50` |
| Older-donor clone ESS | at least `5` |
| Max older-donor clone weight share | at most `30%` |
| Positive worker-donor clone count | at least `50` |
| Worker-donor clone ESS | at least `10` |
| Max worker-donor clone weight share | at most `20%` |

These checks are safety rails for diagnostics and provenance, not a replacement
for exact production data.

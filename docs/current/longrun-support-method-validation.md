# Long-Run Support Method Validation

This note records the first support-method holdout check for the 2100 long-run
dataset. The goal is to test whether donor-backed support and thin reweighting
only differ mechanically, or whether they place tax-relevant income in different
parts of the tax schedule.

Generated artifact:

- `tmp/longrun_support_validation/longrun_support_method_validation_2100.csv`
- `tmp/longrun_support_validation/longrun_support_method_validation_2100.md`

Command:

```bash
uv run --extra us python /Users/maxghenis/PolicyEngine/crfb-tob-impacts/scripts/compare_longrun_support_methods.py \
  --year 2100 \
  --tax-assumption-module /Users/maxghenis/PolicyEngine/_codex_prs/us-data-main-1.113.1/policyengine_us_data/datasets/cps/long_term/tax_assumptions.py
```

## 2100 Results

Both datasets hit the Trustees aggregate calibration targets for Social Security
benefits, taxable payroll, OASDI taxation of benefits, and HI taxation of
benefits. A separate external holdout from
[SSA Trustees Table IV.B3](https://www.ssa.gov/OACT/TR/2025/lr4b3.html)
compares covered-worker and beneficiary counts that were not used as calibration
targets. The PolicyEngine counts are annual positive-amount proxies, while the
Trustees beneficiary counts are current-payment status as of June 30, so this is
a directional validation check rather than an exact constraint.

| Metric | Donor support | Thin reweighting |
|---|---:|---:|
| Positive-weight households | 41,694 | 5,216 |
| Overall effective sample size | 463 | 555 |
| OASDI TOB contributor ESS | 47 | 56 |
| HI TOB contributor ESS | 43 | 51 |
| Baseline income tax | $35.683T | $37.031T |
| Baseline taxable income | $199.863T | $207.714T |
| Option 12 income-tax impact | -$1.221T | -$1.023T |
| Option 12 tax on employer inclusion | $2.642T | $2.839T |
| Effective tax rate on employer inclusion | 19.7% | 21.0% |

External Trustees holdouts:

| Holdout | Trustees target | Donor support | Donor error | Thin reweighting | Thin error |
|---|---:|---:|---:|---:|---:|
| Covered workers | 228.446M | 246.192M | +7.8% | 238.475M | +4.4% |
| OASI beneficiaries | 96.987M | 88.382M | -8.9% | 74.428M | -23.3% |
| DI beneficiaries | 13.326M | 8.214M | -38.4% | 7.501M | -43.7% |
| OASDI beneficiaries | 110.313M | 96.595M | -12.4% | 81.929M | -25.7% |

## Interpretation

The support diagnostics are mixed. Thin reweighting has higher total ESS and
slightly higher TOB contributor ESS, so it is not automatically worse on generic
weight concentration metrics.

The external holdouts are mixed but mostly favor donor-backed support. Thin
reweighting is closer on covered workers. Donor support is closer on OASI, DI,
and total OASDI beneficiary counts, which are especially relevant because total
benefit dollars are one of the hard calibration targets.

The policy-relevant tax-base holdouts also favor donor-backed support. Thin
reweighting puts more employer-payroll inclusion into high-tax units:

| Option 12 exposure group | Donor support | Thin reweighting |
|---|---:|---:|
| Employer inclusion above $1M taxable income | 56.1% | 62.1% |
| Employer inclusion above $2M taxable income | 28.5% | 36.8% |
| Employer inclusion in 60%+ marginal-rate units | 37.5% | 41.5% |
| Option 12 tax delta above $2M taxable income | 39.0% | 48.3% |

This is why option 12 differs materially even when the aggregate Trustees
targets match. Thin reweighting appears to preserve fewer base households and
assigns more of the 2100 payroll-tax inclusion to high-income, high-rate units.

## Decision Rule

For publishable results, prefer the method that is stable on policy-relevant
holdouts, not simply the method with fewer synthetic records. Based on this
2100 check, donor-backed support remains the better default for publication.
Thin reweighting should be retained as a robustness check unless future holdout
targets close the beneficiary-count, baseline income-tax, and marginal-rate-
exposure gaps.

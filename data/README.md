# Trust Fund Gap Data for Option 13

This file documents `trust_fund_gaps.csv`, which provides the data needed to implement Option 13's "balanced fix" baseline.

## What is the "Gap"?

Each trust fund has a **gap** when it pays out more in benefits than it collects in taxes:

```
Gap = Cost Rate − Income Rate
```

Where:
- **Cost Rate** = Benefits paid ÷ Taxable Payroll (as % of payroll)
- **Income Rate** = Payroll taxes + other income ÷ Taxable Payroll (as % of payroll)

### Why express as % of payroll?

Expressing the gap as a percentage of taxable payroll makes it:
1. Comparable across years (inflation-adjusted)
2. Directly translatable to policy fixes (e.g., "raise payroll tax by X%")

### Example

If OASDI has:
- Cost rate: 17% (pays $1.7T in benefits on $10T taxable payroll)
- Income rate: 13.5% (collects $1.35T in payroll taxes + TOB)
- **Gap: 3.5%** of payroll ($350B shortfall)

To close a 3.5% gap with a "balanced fix":
- 50% via benefit cuts → reduce cost rate by 1.75%
- 50% via tax increases → raise payroll tax by 1.75%

---

## File: `trust_fund_gaps.csv`

| Column | Description |
|--------|-------------|
| `year` | Calendar year (2026-2100) |
| `oasdi_cost_rate` | OASDI benefits paid as % of taxable payroll |
| `oasdi_income_rate` | OASDI income (payroll tax + TOB) as % of taxable payroll |
| `oasdi_gap_pct` | OASDI gap = cost − income |
| `hi_cost_rate` | Medicare HI (Part A) spending as % of taxable payroll |
| `hi_income_rate` | HI income as % of taxable payroll |
| `hi_gap_pct` | HI gap = cost − income |

---

## Key Numbers from 2025 Trustees Reports

| Metric | OASDI | Medicare HI |
|--------|-------|-------------|
| 75-year actuarial deficit | **3.82%** of payroll | **0.42%** of payroll |
| Current payroll tax rate | 12.4% (6.2% + 6.2%) | 2.9% (1.45% + 1.45%) |
| Trust fund depletion year | 2034 | 2033 |
| Cost rate trajectory | 15% → 19% → 18% | 3.4% → 4.7% → 4.5% |

---

## How Option 13 Uses This Data

Option 13 scores Option 12 against a "balanced fix" baseline where, starting in 2035:

**For OASDI (3.82% gap):**
- 50% via benefit cuts = 1.91% (not modeled in PolicyEngine)
- 50% via payroll tax increase = 1.91% → rate goes from 12.4% to 14.31%

**For HI (0.42% gap):**
- 50% via benefit cuts = 0.21% (not modeled)
- 50% via payroll tax increase = 0.21% → rate goes from 2.9% to 3.11%

The payroll tax increases are implemented in `src/reforms.py` via `get_balanced_fix_dict()`.

---

## Data Sources

**OASDI:**
- [SSA 2025 OASDI Trustees Report](https://www.ssa.gov/OACT/TR/2025/)
- [Boston College CRR Analysis](https://crr.bc.edu/social-securitys-financial-outlook-the-2025-update-in-perspective/)

**Medicare HI:**
- [CMS 2025 Medicare Trustees Report](https://www.cms.gov/oact/tr/2025)
- [CRFB Analysis](https://www.crfb.org/papers/analysis-2025-medicare-trustees-report)

---

## Methodology Notes

### Data Quality

The **key anchor points** (75-year deficits, depletion dates, cost rate endpoints) come directly from the Trustees Reports.

**Intermediate year values are interpolations** based on the trajectories described in the reports. For official year-by-year projections, download:
- `SingleYearTRTables_TR2025.xlsx` from [SSA](https://www.ssa.gov/OACT/TR/2025/)
- Supplementary tables from [CMS](https://www.cms.gov/oact/tr/2025)

### Why Start in 2035?

Both trust funds are projected to be depleted by 2034. A "balanced fix" starting in 2035 represents a scenario where Congress acts proactively to restore solvency, rather than allowing automatic benefit cuts when reserves run out.

### Why 50/50 Split?

The 50% benefit cuts / 50% tax increases split is a common assumption in solvency analyses. It represents a politically balanced approach where both beneficiaries and workers share the adjustment burden equally.

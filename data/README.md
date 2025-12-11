# SSA Taxation of Benefits Baseline Data

This directory contains baseline projections for Social Security taxation of benefits (TOB) revenue, split between the OASDI (Social Security) and HI (Medicare Hospital Insurance) trust funds.

## Data Sources

**OASDI Data:** SSA 2025 OASDI Trustees Report - Intermediate Assumptions
- Available from: https://www.ssa.gov/OACT/TR/2025/
- **Table IV.A3** - Operations of the OASI and DI Trust Funds (short-range): Direct dollar values for 2024-2034
- **Table IV.B2** - Components of Annual Income Rates: OASDI taxation of benefits as % of taxable payroll (for 2035+)
- **Table VI.G6** - Selected Economic Variables: Taxable payroll projections in billions (for 2035+)
- Single Year Tables Excel file: `SingleYearTRTables_TR2025.xlsx`

**HI Data:** CMS 2025 Medicare Trustees Report - Intermediate Assumptions
- Available from: https://www.cms.gov/oact/tr/2025
- **"Medicare Sources of Non-Interest Income"** table: "Tax on Benefits" column - Direct dollar values for all years 2024-2099
- Supplementary Tables zip file: `tr2025-tables-figures.zip`

## Files

### `ssa_tob_baseline_75year.csv`

75-year projections of taxation of benefits revenue (2024-2099).

| Column | Description |
|--------|-------------|
| `year` | Calendar year (2024-2099) |
| `tob_oasdi_billions` | OASDI trust fund TOB revenue ($B) - **Direct values 2024-2034**, calculated 2035+ |
| `tob_hi_billions` | Medicare HI trust fund TOB revenue ($B) - **Direct values all years** from CMS |
| `tob_total_billions` | Total TOB revenue ($B) = OASDI + HI |
| `oasdi_share` | OASDI share of total TOB (varies by year) |
| `hi_share` | HI share of total TOB (varies by year) |

## Methodology

### Background: Taxation of Benefits Structure

Social Security benefits became partially taxable under two pieces of legislation:

1. **1983 Amendments (Tier 1):** Up to 50% of benefits taxable for beneficiaries with income above:
   - $25,000 (single filers)
   - $32,000 (married filing jointly)
   - **Revenue goes to: OASDI Trust Funds**

2. **1993 Omnibus Budget Reconciliation Act (Tier 2):** Additional taxation up to 85% of benefits for income above:
   - $34,000 (single filers)
   - $44,000 (married filing jointly)
   - **Revenue goes to: HI (Medicare) Trust Fund**

**Critical:** These thresholds are **not indexed to inflation**, so more beneficiaries become subject to taxation each year as nominal incomes rise.

### Step 1: Extract OASDI TOB Data (from SSA)

**For years 2024-2034 (Short-Range):** Direct dollar values from Table IV.A3 "Taxation of benefits" column.

**For years 2035-2099 (Long-Range):** Calculated from:
- Table IV.B2: OASDI taxation of benefits as % of taxable payroll
- Table VI.G6: Taxable payroll projections in billions

```
OASDI TOB ($B) = (OASDI TOB % / 100) × Taxable Payroll ($B)
```

The calculated values match direct values within ~0.5% where they overlap (2024-2034), confirming the methodology.

### Step 2: Extract HI TOB Data (from CMS)

From the CMS Medicare Trustees Report supplementary table "Medicare Sources of Non-Interest Income", we extract the "Tax on Benefits" column which contains HI taxation of benefits in millions of dollars.

```
HI TOB ($B) = Tax on Benefits (millions) / 1000
```

### Step 3: Calculate Total and Shares

```
Total TOB = OASDI TOB + HI TOB
OASDI Share = OASDI TOB / Total TOB
HI Share = HI TOB / Total TOB
```

### Key Finding: The OASDI/HI Split Varies by Year

Unlike our earlier modeled approach, the authoritative data shows the split is **not constant**:

| Year | OASDI Share | HI Share | Notes |
|------|-------------|----------|-------|
| 2024 | 58.1% | 41.9% | Actual |
| 2025 | 59.6% | 40.4% | Projected |
| 2030 | 57.4% | 42.6% | Projected |
| 2050 | 54.7% | 45.3% | Projected |
| 2099 | 54.4% | 45.6% | Projected |

The HI share gradually increases over time as more beneficiaries exceed the Tier 2 threshold ($34k/$44k), but the change is modest (~3 percentage points over 75 years) since most of the shift already occurred between 1993-2024.

### Validation

**2024 Values:**
- OASDI TOB: $55.1B (58.1%) - Direct from SSA Table IV.A3
- HI TOB: $39.8B (41.9%) - Direct from CMS
- Total TOB: $94.9B

These are the exact values reported in both Trustees Reports.

## Policy Impact Trust Fund Breakdown

### `impacts_trust_breakdown.csv`

Trust fund breakdown of policy reform impacts (2026-2100) for all 8 reform options.

| Column | Description |
|--------|-------------|
| `reform_name` | Reform identifier (option1-option8) |
| `year` | Calendar year (2026-2100) |
| `baseline_revenue` | Baseline total income tax revenue ($B) |
| `reform_revenue` | Reform total income tax revenue ($B) |
| `revenue_impact` | Total income tax impact ($B) |
| `baseline_tob_oasdi` | Official OASDI baseline TOB ($B) |
| `baseline_tob_medicare_hi` | Official HI baseline TOB ($B) |
| `baseline_tob_total` | Official total baseline TOB ($B) |
| `reform_tob_oasdi` | OASDI TOB under reform ($B) |
| `reform_tob_medicare_hi` | HI TOB under reform ($B) |
| `reform_tob_total` | Total TOB under reform ($B) |
| `tob_oasdi_impact` | Change in OASDI TOB ($B) |
| `tob_medicare_hi_impact` | Change in HI TOB ($B) |
| `tob_total_impact` | Change in total TOB ($B) |
| `scoring_type` | Scoring method (static) |

### Methodology for Trust Fund Impact Allocation

**Baseline Values:** All reforms use the same official SSA/CMS baseline projections from `ssa_tob_baseline_75year.csv`.

**Reform Impact Allocation:**

1. **Options 1 & 5 (Full Repeal, Roth-Style Swap):** These reforms eliminate all taxation of benefits revenue.
   - Reform TOB values = $0 for both OASDI and HI
   - Impact = negative of baseline (full elimination)

2. **All Other Options (2, 3, 4, 6, 7, 8):** Reform impacts are taken directly from PolicyEngine microsimulation results.
   - Baseline values use official SSA/CMS projections
   - Reform values = Official Baseline + PolicyEngine Impact

## Key Data Points

| Year | Total TOB | OASDI | HI | OASDI % | HI % | Source |
|------|-----------|-------|-----|---------|------|--------|
| 2024 | $94.9B | $55.1B | $39.8B | 58.1% | 41.9% | Direct |
| 2025 | $100.8B | $60.1B | $40.7B | 59.6% | 40.4% | Direct |
| 2026 | $128.9B | $76.7B | $52.2B | 59.5% | 40.5% | Direct |
| 2027 | $143.7B | $83.1B | $60.6B | 57.8% | 42.2% | Direct |
| 2030 | $179.9B | $103.3B | $76.6B | 57.4% | 42.6% | Direct |
| 2034 | $242.7B | $138.2B | $104.5B | 56.9% | 43.1% | Direct |
| 2050 | $507.3B | $277.3B | $230.0B | 54.7% | 45.3% | Calc'd |
| 2075 | $1,503.3B | $815.1B | $688.2B | 54.2% | 45.8% | Calc'd |
| 2099 | $3,716.4B | $2,022.2B | $1,694.2B | 54.4% | 45.6% | Calc'd |

**Note:** "Direct" = OASDI from Table IV.A3 + HI from CMS. "Calc'd" = OASDI calculated from % × payroll (years 2035+).

## References

- SSA 2025 OASDI Trustees Report: https://www.ssa.gov/OACT/TR/2025/
- CMS 2025 Medicare Trustees Report: https://www.cms.gov/oact/tr/2025
- SSA Office of the Chief Actuary - Provisions Affecting Taxation of Benefits: https://www.ssa.gov/oact/solvency/provisions/taxbenefit.html

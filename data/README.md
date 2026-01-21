# Trust Fund Gap Data for Option 13

## Overview

Option 13 implements a "balanced fix" baseline starting in 2035 that closes trust fund gaps via:
1. **50% payroll tax increases** (split employee/employer)
2. **50% SS benefit cuts** (with TOB feedback adjustment)

---

## Gap Calculation Methodology

### Our Simulation Approach

For each year, we calculate gaps from PolicyEngine microsimulation:

**SS (OASDI) Gap:**
```
SS Income = employee_ss_tax + employer_ss_tax + tob_oasdi
SS Outgo  = social_security (benefits)
SS Gap    = SS Income - SS Outgo
```

**HI (Medicare) Gap:**
```
HI Income = employee_medicare_tax + employer_medicare_tax + tob_hi
HI Outgo  = HI Cost Rate × HI Taxable Payroll (from Trustees)
HI Gap    = HI Income - HI Outgo
```

Note: We calculate HI outgo from Trustees data because Medicare expenditures aren't in our microsimulation.

### Gap Closing Formula (Two-Stage Approach)

Option 13 is the "traditional fix" baseline - it does NOT include the employer payroll tax reform (taxing employer contributions as income). This provides an apples-to-apples comparison with current law.

Starting 2035, for each year:

**Stage 1: Apply benefit cuts, measure remaining gaps**
```
benefit_cut = ss_shortfall * 0.5  # Straight 50% cut
benefit_multiplier = 1 - (benefit_cut / ss_benefits)

# Run simulation with benefit cuts only (no other reforms)
# Measure remaining SS and HI gaps (includes TOB effects naturally)
remaining_ss_gap = stage1_ss_gap  # Payroll income - benefits
remaining_hi_gap = stage1_hi_gap  # Payroll income - expenditures
```

**Stage 2: Close remaining gaps with rate increases**
```
ss_rate_increase = abs(remaining_ss_gap) / oasdi_taxable_payroll  # If deficit
hi_rate_increase = abs(remaining_hi_gap) / hi_taxable_payroll    # Always an increase (no surplus)
```
Each rate change is split equally between employee and employer.

**Implementation:**
- Benefit cuts: Use `simulation.set_input("social_security", year, reduced_values)` BEFORE any `.calculate()` calls
- Tax rates: Use `Reform.from_dict()` to modify payroll tax parameters
- Two simulations: Stage 1 measures gaps after benefit cuts, Stage 2 applies rate increases

---

## Data Sources

### Trustees 2025 Data

| File | Contents | Source |
|------|----------|--------|
| `hi_expenditures_tr2025.csv` | HI expenditures by year (2035-2099) | Derived from CMS Trustees Report |

**HI Expenditures** were pre-calculated from Trustees data:
```
HI Expenditures = Cost Rate × HI Taxable Payroll
Example 2035: 4.31% × $20.3T = $875B
```

---

## Validation Against Trustees Data

### 2035 Comparison

| Metric | Our Simulation | Trustees 2025 |
|--------|---------------|---------------|
| HI Payroll Taxes | $535.6B | ~$589B (2.9% × $20.3T) |
| HI TOB | $112.0B | ~$105B (2034 value) |
| HI Expenditures | $875.0B | $875B (from cost rate) |
| **HI Gap** | **-$227.4B** | **-$113.7B** |

### Known Discrepancies

1. **Payroll taxes ~$53B lower:** Our microsimulation dataset doesn't perfectly match Trustees aggregate economic projections.

2. **Gap ~$114B larger:** Trustees income includes interest on trust fund assets (~$115B historically), which we don't model. By 2035, interest is near zero as trust fund depletes, so this discrepancy shrinks.

3. **Trustees detailed table stops at 2034:** The "Operations of HI Trust Fund" table only goes through 2034. For 2035+, we use cost/income rates × taxable payroll.

### Validation Method

Compare simulation outputs against:
- Trustees Report "Operations of the Hospital Insurance (HI) Trust Fund" table (through 2034)
- `hi_expenditures_tr2025.csv` (2035+)

---

## Example: 2035 Gap Closing

**Baseline gaps:**
- SS Gap: -$556.0B
- HI Gap: -$227.4B

**Stage 1 - Benefit cuts only:**
- Benefit cut: $278B (50% of SS gap)
- Benefit multiplier: 1 - ($278B / $2,630B) = 0.894 (10.6% cut)
- Run simulation → measure remaining gaps (includes TOB losses from reduced benefits)

**Stage 2 - Rate increases to close remaining gaps:**
- SS remaining gap → calculate rate increase
- HI remaining gap → calculate rate increase

**Result:**
- SS Gap: ~$0 ✓
- HI Gap: ~$0 ✓
- Combined Gap: ~$0 ✓

---

## References

- [SSA 2025 OASDI Trustees Report](https://www.ssa.gov/OACT/TR/2025/)
- [CMS 2025 Medicare Trustees Report](https://www.cms.gov/oact/tr/2025)
- [CRFB Analysis](https://www.crfb.org/papers/analysis-2025-medicare-trustees-report)

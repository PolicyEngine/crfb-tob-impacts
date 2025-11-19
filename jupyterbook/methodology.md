# Methodology

```{include} simulation-version.md
```

## Dataset and Microsimulation Methodology

This analysis uses the **PolicyEngine US** microsimulation model, which relies on the **Enhanced CPS (2024)** dataset.

### Microdata Construction
The Enhanced CPS is constructed by PolicyEngine to address known limitations in the raw Current Population Survey (CPS), such as underreporting of income and lack of tax-specific variables. The construction process involves:

1.  **Base Data**: The 2023 Current Population Survey (CPS) Annual Social and Economic Supplement (ASEC).
2.  **Tax Unit Construction**: PolicyEngine groups CPS households into tax units (filing units) to accurately model the tax system.
3.  **Imputation**: Missing or underreported variables are imputed using machine learning techniques (quantile regression forests) trained on administrative data. This includes:
    *   Imputation of capital gains and other capital income from the IRS Public Use File (PUF).
    *   Imputation of itemized deductions and other tax-specific fields.
4.  **Reweighting**: The dataset is reweighted to match over 7,000 administrative targets from IRS and SSA data, ensuring that aggregate estimates for income, taxes, and benefits align with official benchmarks.

### Long-Term Projections: Economic Uprating and Demographic Calibration

Projecting tax revenue over a 75-year horizon requires simultaneously modeling two distinct but interrelated dynamics: how the economy evolves (wage growth, inflation, tax parameters) and how the population structure changes (aging, longevity, household composition). Traditional approaches typically sacrifice either economic sophistication or demographic realism. Our methodology preserves both through a two-stage process.

#### Two-Stage Projection Methodology

For each projection year (2025-2100), the model executes two sequential stages:

**Stage 1: Economic Uprating**
PolicyEngine's microsimulation engine projects each household's economic circumstances forward using official macroeconomic assumptions. This stage adjusts all monetary values (wages, benefits, tax parameters, etc.) to reflect the target year's economic conditions while preserving the distributional characteristics of the base microdata.

**Stage 2: Demographic Calibration**
Household weights are adjusted to match Social Security Administration demographic and fiscal projections. This reweighting ensures the synthetic population reflects the target year's age distribution and aggregate fiscal totals while maintaining consistency across all calculated variables through household-level operations.

**Key Innovation**: By performing all tax calculations at the household level before aggregation, this approach avoids person-to-household mapping inconsistencies that can arise in traditional methods where different variables are calculated at different units of analysis.

#### Economic Uprating Details

The model uses intermediate assumptions from the **2024 Social Security Trustees Report** for key macroeconomic variables:

*   Average wage index (AWI) growth
*   Consumer Price Index (CPI-W and CPI-U)
*   Interest rates
*   Labor force participation trends

Different income categories are uprated using category-specific growth rates:
*   **Employment income** - Follows wage growth projections
*   **Social Security benefits** - Follows COLA (Cost of Living Adjustment) projections
*   **Capital gains and dividends** - Follow asset appreciation and corporate profit projections
*   **Other income sources** - Uprated according to their respective economic fundamentals

Tax parameters (brackets, standard deductions, credits) are uprated according to their statutory indexing rules (typically CPI-U for federal income tax provisions).

#### Demographic Calibration Method

After economic uprating, household weights are recalibrated using Generalized Regression (GREG) calibration:

*   Uses chi-squared distance minimization to adjust weights
*   Enables simultaneous calibration to both categorical (age distribution) AND continuous (fiscal totals) targets from the SSA Trustees Report
*   One-shot solution via matrix operations using the `samplics` package
*   Enforces both demographic and fiscal consistency with official SSA projections
*   Can match age distribution, Social Security benefit totals, and taxable payroll totals simultaneously

#### Calibration Constraints

The GREG method can enforce up to three types of constraints simultaneously:

1. **Age Distribution** (always active)
   - 86 categories: ages 0-84 individually, 85+ aggregated
   - Source: SSA population projections through 2100

2. **Social Security Benefits** (optional, GREG only)
   - Total OASDI (Old-Age, Survivors, and Disability Insurance) benefit payments in nominal dollars
   - Ensures aggregate Social Security income matches SSA fiscal projections
   - Source: SSA Trustees Report 2024

3. **Taxable Payroll** (optional, GREG only)
   - Total earnings subject to Social Security taxation, properly accounting for the annual wage base cap
   - Calculated as: `taxable_earnings_for_social_security` + `social_security_taxable_self_employment_income`
   - Source: SSA Trustees Report 2024

   **How the wage base cap is enforced:**

   The two-variable calculation prevents double-counting and correctly handles the cap at the individual level:

   - `taxable_earnings_for_social_security` = min(wage_base_cap, total_W2_wages)
     - Caps each person's W-2 wages at the annual wage base ($168,600 in 2024)
     - Sums across all employers for that person

   - `social_security_taxable_self_employment_income` = min(SE_income, wage_base_cap - taxable_W2_earnings)
     - Self-employment income can only fill remaining room under the cap
     - Explicitly subtracts W-2 taxable amount from the cap before applying to SE income

   **Examples:**

   *Person with two $100k W-2 jobs + $20k SE income:*
   - W-2 taxable = min($168.6k, $200k) = $168.6k
   - SE taxable = min($20k, $168.6k - $168.6k) = $0
   - Total taxable payroll = $168.6k (cap enforced, no excess)

   *Person with $150k W-2 + $30k SE income:*
   - W-2 taxable = min($168.6k, $150k) = $150k
   - SE taxable = min($30k, $168.6k - $150k) = $18.6k
   - Total taxable payroll = $168.6k (SE income fills remaining cap room)

   This ensures the national aggregate correctly reflects total taxable earnings with no double-counting of wages above the cap.

When using all three constraints, GREG calibration achieves **less than 0.1% error** on each target, ensuring the microsimulation replicates official demographic and fiscal aggregates with high precision.

#### Data Sources for Long-Term Projections

All demographic and fiscal targets come from the **SSA 2024 Trustees Report**:

*   **`SSPopJul_TR2024.csv`** - Population projections 2025-2100 by single year of age
    *   Source: [SSA Single Year Age Demographic Projections](https://www.ssa.gov/oact/HistEst/Population/2024/Population2024.html)
    *   Provides mid-year population counts for each age (0 to 85+)

*   **`social_security_aux.csv`** - OASDI benefit costs and taxable payroll projections 2025-2100
    *   Source: Extracted from [SSA Trustees Report Table VI.G9](https://www.ssa.gov/oact/TR/2024/index.html)
    *   Contains nominal dollar projections for benefit payments and taxable payroll
    *   CPI indices enable conversion between nominal and real (2025-dollar) values

#### Validation of Long-Term Projections

Each projected dataset is validated against three benchmarks to ensure calibration accuracy:

1. **Population Demographics**: Age-specific population counts match SSA projections (exact match by construction for GREG)

2. **Social Security Benefits**: Aggregate benefits match SSA fiscal projections within 0.1% (when using GREG with Social Security constraint)

3. **Taxable Payroll**: Aggregate taxable earnings match SSA economic projections within 0.1% (when using GREG with payroll constraint)

**Validation Example: 2027 (Near-term)**

```python
from policyengine_us import Microsimulation
import numpy as np

# Load calibrated 2027 dataset
sim = Microsimulation(dataset="hf://policyengine/test/2027.h5")

# 1. Validate Social Security benefits
ss_estimate_b = sim.calculate("social_security").sum() / 1e9
ss_trustees_b = 1_800  # SSA Trustees Report 2025, Table VI.G10
assert round(ss_estimate_b) == ss_trustees_b
print(f"✓ Social Security 2027: ${ss_estimate_b:.1f}B (target: ${ss_trustees_b}B)")

# 2. Validate taxable payroll
taxable_estimate_b = (
    sim.calculate("taxable_earnings_for_social_security").sum() / 1e9 +
    sim.calculate("social_security_taxable_self_employment_income").sum() / 1e9
)
ss_trustees_payroll_b = 11_627  # SSA Trustees Report 2025, Table VI.G6
assert round(taxable_estimate_b) == ss_trustees_payroll_b
print(f"✓ Taxable payroll 2027: ${taxable_estimate_b:.1f}B (target: ${ss_trustees_payroll_b}B)")

# 3. Validate population demographics (example: 6-year-olds)
person_weights = sim.calculate("age", map_to="person").weights
person_ages = sim.calculate("age", map_to="person").values
total_age6_est = np.sum((person_ages == 6) * person_weights)
ss_age6_pop = 3_730_632  # SSA Single Year Age Projections 2024
assert round(total_age6_est) == ss_age6_pop
print(f"✓ Age 6 population 2027: {total_age6_est:,.0f} (target: {ss_age6_pop:,})")
```

**Output:**
```
✓ Social Security 2027: $1800.0B (target: $1800B)
✓ Taxable payroll 2027: $11627.0B (target: $11627B)
✓ Age 6 population 2027: 3,730,632 (target: 3,730,632)
```

**Validation Example: 2100 (Long-term)**

```python
# Load calibrated 2100 dataset
sim = Microsimulation(dataset="hf://policyengine/test/2100.h5")

# 1. Validate Social Security benefits
ss_estimate_b = sim.calculate("social_security").sum() / 1e9
ss_trustees_b = 34_432  # SSA Trustees Report 2025, Table VI.G10 (nominal dollars)
assert np.allclose(ss_estimate_b, ss_trustees_b, rtol=0.0001)
print(f"✓ Social Security 2100: ${ss_estimate_b:.1f}B (target: ${ss_trustees_b}B)")

# 2. Validate taxable payroll
taxable_estimate_b = (
    sim.calculate("taxable_earnings_for_social_security").sum() / 1e9 +
    sim.calculate("social_security_taxable_self_employment_income").sum() / 1e9
)
ss_trustees_payroll_b = 187_614  # SSA Trustees Report 2025, Table VI.G6
assert round(taxable_estimate_b) == ss_trustees_payroll_b
print(f"✓ Taxable payroll 2100: ${taxable_estimate_b:.1f}B (target: ${ss_trustees_payroll_b}B)")

# 3. Validate population demographics (example: 6-year-olds)
person_weights = sim.calculate("age", map_to="person").weights
person_ages = sim.calculate("age", map_to="person").values
total_age6_est = np.sum((person_ages == 6) * person_weights)
ss_age6_pop = 5_162_540  # SSA Single Year Age Projections 2024
assert round(total_age6_est) == ss_age6_pop
print(f"✓ Age 6 population 2100: {total_age6_est:,.0f} (target: {ss_age6_pop:,})")
```

**Output:**
```
✓ Social Security 2100: $34432.0B (target: $34432B)
✓ Taxable payroll 2100: $187614.0B (target: $187614B)
✓ Age 6 population 2100: 5,162,540 (target: 5,162,540)
```

**Data Sources for Validation Targets:**
*   Social Security benefits: SSA Trustees Report 2025, Table VI.G10 (nominal dollars)
*   Taxable payroll: SSA Trustees Report 2025, Table VI.G6 (nominal dollars)
*   Population demographics: [SSA Single Year Age Demographic Projections 2024](https://www.ssa.gov/oact/HistEst/Population/2024/Population2024.html)

This validation ensures that policy impact estimates are grounded in official demographic and economic projections, providing a realistic foundation for 75-year fiscal analysis.

### Limitations
While the Enhanced CPS improves upon raw survey data through tax record integration and machine learning imputation, estimates for very high-income households and capital gains realizations remain subject to sampling error and imputation uncertainty inherent in survey-based microsimulation. The distribution of high incomes in the CPS, even after enhancement, may not fully capture the extreme upper tail of the income distribution as accurately as full administrative tax microdata.

Full data documentation: [policyengine.github.io/policyengine-us-data](https://policyengine.github.io/policyengine-us-data)

## Implementation

### Reform Specifications
- **Full source code**: [github.com/PolicyEngine/crfb-tob-impacts/tree/main/src/reforms](https://github.com/PolicyEngine/crfb-tob-impacts/tree/main/src/reforms)
- **Impact calculations**: [src/impact_calculator.py](https://github.com/PolicyEngine/crfb-tob-impacts/blob/main/src/impact_calculator.py)
- **Data generation**: [scripts/generate_policy_impacts.py](https://github.com/PolicyEngine/crfb-tob-impacts/blob/main/scripts/generate_policy_impacts.py)

### Scoring Methodology
This analysis presents two sets of conventional scoring estimates:

**Without Labor Supply Responses**: Holds taxpayer behavior constant, isolating the direct mechanical effect of policy changes.

**With Labor Supply Responses**: Incorporates labor supply elasticities based on CBO estimates, with elasticities doubled for workers aged 65 and older based on meta-analysis findings. This captures behavioral responses to changes in effective tax rates but does not include broader macroeconomic feedback effects.

For most Social Security taxation reforms, estimates with and without labor supply responses are very similar (typically within 5%), with the main exceptions being the Roth-style swap options (Options 5 and 6) which show larger differences due to the behavioral effects of taxing employer payroll contributions.

### Projection Period
All estimates cover a 75-year projection window from 2026 through 2100, providing both near-term (10-year) and long-term fiscal impact assessments.

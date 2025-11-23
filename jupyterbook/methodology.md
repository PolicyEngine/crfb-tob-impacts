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

### Long-Term Projections (Uprating)
To project fiscal and household impacts through 2100, PolicyEngine applies economic uprating factors to the microdata:

*   **Economic Assumptions**: The model uses intermediate assumptions from the **2024 Social Security Trustees Report** for key macroeconomic variables, including:
    *   Average wage index (AWI) growth
    *   Consumer Price Index (CPI-W and CPI-U)
    *   Interest rates
    *   Labor force participation trends
*   **Microdata Aging**: Individual records in the 2023 microdata are "aged" or uprated to future years by adjusting monetary values (wages, benefits, etc.) according to these macroeconomic growth factors. This allows the model to simulate the 2026-2100 period while maintaining the distributional characteristics of the underlying population.

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
All estimates cover a 75-year projection window from 2026 through 2100, providing both near-term (10-year) and long-term fiscal impact assessments.\\$
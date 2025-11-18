# Methodology

```{include} simulation-version.md
```

## Dataset

This analysis uses the **Enhanced CPS (2024)**, PolicyEngine's enhanced version of the 2023 Current Population Survey with:
- Imputation of tax variables using quantile regression forests
- Reweighting to over 7,000 targets from administrative sources

Full documentation: [policyengine.github.io/policyengine-us-data](https://policyengine.github.io/policyengine-us-data)

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

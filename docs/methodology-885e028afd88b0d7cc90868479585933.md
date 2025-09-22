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

### Static Analysis
All estimates use static microsimulation without behavioral responses.

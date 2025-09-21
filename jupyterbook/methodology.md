# Methodology

```{include} simulation-version.md
```

## Dataset

This analysis uses the **Enhanced CPS (2024)**, PolicyEngine's enhanced version of the 2023 Current Population Survey with:
- **100,827 households** representing the US population
- **232,850 individuals** with detailed income and demographic data
- Statistical matching with IRS Statistics of Income
- Reweighting to match national totals

Full documentation: [policyengine.github.io/policyengine-us-data](https://policyengine.github.io/policyengine-us-data)

## Implementation

### Reform Specifications
- **Full source code**: [github.com/PolicyEngine/crfb-tob-impacts/tree/main/src/reforms](https://github.com/PolicyEngine/crfb-tob-impacts/tree/main/src/reforms)
- **Impact calculations**: [src/impact_calculator.py](https://github.com/PolicyEngine/crfb-tob-impacts/blob/main/src/impact_calculator.py)
- **Data generation**: [scripts/generate_policy_impacts.py](https://github.com/PolicyEngine/crfb-tob-impacts/blob/main/scripts/generate_policy_impacts.py)

### Static Analysis
All estimates use static microsimulation without behavioral responses.

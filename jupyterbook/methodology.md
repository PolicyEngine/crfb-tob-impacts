# Methodology

This analysis uses the PolicyEngine US microsimulation model to estimate the fiscal and household impacts of seven Social Security benefit taxation reform options. This page describes the methodological approach, data sources, and key assumptions.

## Simulation Model

```{include} simulation-version.md
```

## Data Sources

### Enhanced Current Population Survey (CPS)
The analysis is based on PolicyEngine's enhanced Current Population Survey (CPS) microdata. The CPS is a monthly household survey conducted by the U.S. Census Bureau that provides comprehensive data on income, employment, and demographics for approximately 60,000 households.

PolicyEngine enhances the CPS data through:
- **Statistical matching** with tax return data to improve income distribution accuracy
- **Imputation** of missing variables needed for tax calculations
- **Reweighting** to match population and income aggregates
- **Uprating** to project values to the analysis period (2026-2035)

### Base Year
All simulations use 2024 as the base year for the underlying microdata, with values projected forward using economic assumptions consistent with Congressional Budget Office projections.

## Reform Specifications

The analysis examines seven distinct policy options:

1. **Full Repeal**: Complete elimination of Social Security benefit taxation
2. **85% Taxation**: Tax 85% of benefits for all recipients regardless of income
3. **85% with Senior Deduction**: 85% taxation with permanent senior deduction extension
4. **$500 Tax Credit**: Replace senior deduction with a nonrefundable $500 credit
5. **Roth-Style Swap**: Eliminate benefit taxation, increase payroll taxes by 2 percentage points
6. **Phased Roth-Style**: Phase in Roth-style swap over 10 years
7. **Eliminate Bonus Senior Deduction**: Remove the temporary $6,000 bonus deduction

## Key Assumptions

### Economic Assumptions
- Inflation adjustments follow CBO projections
- Real wage growth consistent with Social Security Trustees' intermediate assumptions
- No behavioral responses to tax changes (static analysis)

### Tax Law Baseline
The baseline incorporates:
- The One Big Beautiful Bill provisions effective 2025-2028
- Scheduled expiration of temporary provisions
- Current law Social Security benefit taxation thresholds

### Household Simulations
For household impact analysis, we model a representative elderly household with:
- Single filer, age 70
- $30,000 in annual Social Security benefits
- Employment income varying from $0 to $200,000
- Florida residence (no state income tax)
- Standard deduction

## Limitations

### Static Analysis
This analysis uses static microsimulation, which does not account for:
- Behavioral responses to tax changes
- Macroeconomic feedback effects
- Labor supply adjustments
- Savings and retirement timing changes

### Uncertainty
Results are subject to uncertainty from:
- Economic projection variance
- Data imputation accuracy
- Policy implementation details
- Legislative interpretation

## Quality Assurance

All calculations undergo validation through:
- Comparison with external estimates from CBO, JCT, and SSA
- Internal consistency checks across years and scenarios
- Automated testing of reform implementations
- Review of edge cases and boundary conditions

## References

For detailed technical documentation of the PolicyEngine US model, see:
- [PolicyEngine US Model Documentation](https://github.com/PolicyEngine/policyengine-us)
- [Enhanced CPS Methodology](https://github.com/PolicyEngine/policyengine-us-data)

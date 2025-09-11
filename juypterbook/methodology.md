# Methodology

This chapter describes our analytical approach for estimating the budgetary impacts of Social Security benefit taxation reforms. We employ microsimulation modeling using PolicyEngine, an open-source platform that provides detailed estimates of policy changes on federal tax revenue and household-level impacts.

## Microsimulation Framework

### PolicyEngine Platform

Our analysis uses PolicyEngine US, an open-source tax-benefit microsimulation model {cite}`policyengine2024`. PolicyEngine provides several advantages for this analysis:

- **Comprehensive Tax Code Implementation**: Complete modeling of federal income tax provisions, including Social Security benefit taxation rules
- **Current Data**: Based on the most recent enhanced Current Population Survey data (2024)
- **Policy Flexibility**: Allows detailed specification of complex policy reforms
- **Transparency**: Open-source codebase enables verification and replication
- **Validation**: Regular benchmarking against official government estimates

### Data Foundation

The microsimulation is based on the Enhanced Current Population Survey (CPS) for 2024:

- **Sample Size**: Approximately 160,000 individuals in 60,000 households
- **Representative Coverage**: Nationally representative sample weighted to match U.S. population
- **Income Sources**: Detailed information on wages, Social Security benefits, pensions, and other income
- **Demographics**: Age, filing status, state of residence, and other relevant characteristics
- **Enhancement**: Survey data enhanced with statistical matching to capture income and benefit details

### Tax Calculator Engine

PolicyEngine's tax calculator implements current law provisions including:

- Federal income tax brackets and rates
- Standard and itemized deductions
- Social Security benefit taxation rules (current two-tier system)
- Senior deduction provisions
- Credits and other tax preferences
- Alternative Minimum Tax calculations

## Policy Implementation

### Reform Specification

Each policy option is implemented through PolicyEngine's reform system, which allows precise specification of:

**Tax Rate Changes**: Modifying the percentage of Social Security benefits subject to taxation
**Threshold Modifications**: Adjusting or eliminating income thresholds for benefit taxation
**Deduction Changes**: Modifying or eliminating the senior deduction
**Credit Implementation**: Adding new tax credits with specific calculation rules
**Phase-in Schedules**: Implementing gradual policy changes over multiple years

### Baseline Establishment

Our analysis uses a current law baseline that incorporates:

- Existing Social Security benefit taxation rules through 2035
- Scheduled expiration of the bonus senior deduction at end of 2028
- Inflation indexing of tax brackets and standard deductions
- Economic assumptions consistent with current projections

### Policy Reform Implementation

For each of the six policy options, we implement specific parameter changes:

**Option 1 (Full Repeal)**:
```
Social Security taxation rate: 0% (all income levels)
Effective date: January 1, 2026
Senior deduction: Expires 2028 as scheduled
```

**Option 2 (85% Taxation)**:
```
Social Security taxation rate: 85% (all beneficiaries)
Income thresholds: Eliminated
Effective date: January 1, 2026
Senior deduction: Expires 2028 as scheduled
```

**Options 3-6**: Similar detailed parameter specifications based on policy descriptions in Chapter 2.

## Calculation Methodology

### Annual Impact Estimation

For each policy option and year (2026-2035), we calculate:

1. **Baseline Revenue**: Federal income tax revenue under current law
2. **Reform Revenue**: Federal income tax revenue under the policy reform
3. **Budgetary Impact**: Difference between baseline and reform revenue

The impact is calculated as: `Impact = Baseline Revenue - Reform Revenue`

- **Negative values** indicate costs (revenue loss)
- **Positive values** indicate savings (revenue gain)

### Aggregation and Weighting

Individual household impacts are aggregated using CPS survey weights to produce:
- National estimates in nominal dollars
- Results scaled to match official government revenue projections
- Confidence intervals based on survey sampling variation

### 10-Year Budget Window

All results are presented for the standard 10-year budget window (2026-2035) used in federal budget analysis. Annual estimates are:
- Calculated separately for each year to capture policy timing effects
- Summed to produce cumulative 10-year impacts
- Presented in both annual and cumulative formats

## Technical Specifications

### Software Environment

- **PolicyEngine Version**: Latest stable release (2024)
- **Python Version**: 3.10+
- **Key Dependencies**: NumPy, Pandas for data processing
- **Computational Resources**: Analysis performed on standard computing environment

### Data Processing

The analysis workflow includes:

1. **Baseline Calculation**: Pre-compute baseline tax liabilities for all years
2. **Reform Implementation**: Apply policy changes through PolicyEngine reform system
3. **Impact Calculation**: Calculate difference between reform and baseline scenarios
4. **Quality Assurance**: Validate results against known benchmarks
5. **Output Generation**: Format results for analysis and presentation

### Validation Procedures

We validate our methodology through:

**Baseline Validation**: Comparing current law projections to CBO estimates
**Cross-Year Consistency**: Ensuring logical progression of impacts over time
**Distributional Checks**: Verifying that impacts align with policy design
**Sensitivity Analysis**: Testing robustness to key assumptions

## Limitations and Assumptions

### Static Analysis

Our analysis uses static microsimulation, meaning:
- No behavioral responses to tax changes are modeled
- Labor supply, retirement timing, and benefit claiming decisions held constant
- Savings and investment responses not captured
- Economic growth effects not included

### Data Limitations

The Enhanced CPS data has several limitations:
- Survey data may underrepresent very high-income households
- Some income sources may be underreported
- Administrative data matching not available for all variables
- Sample size limits precision for small subgroups

### Policy Implementation

Our policy implementations make several assumptions:
- Full compliance with new tax provisions
- No administrative costs or implementation delays
- Perfect information and understanding by taxpayers
- No interaction with state tax systems

### Economic Assumptions

The analysis assumes:
- Current law economic assumptions (inflation, wage growth)
- No macroeconomic feedback effects from policy changes
- Stable demographic and benefit program parameters
- No changes to Social Security benefit levels or eligibility

## Comparison to Other Methods

### Advantages of Microsimulation

Compared to other estimation methods, microsimulation provides:
- **Detailed Distributional Analysis**: Household-level impacts across income ranges
- **Policy Precision**: Exact implementation of complex tax provisions
- **Flexibility**: Ability to analyze multiple policy variants
- **Transparency**: Clear link between policy parameters and estimated impacts

### Limitations Relative to Dynamic Models

Unlike dynamic economic models, our approach does not capture:
- Behavioral responses and feedback effects
- Macroeconomic impacts on economic growth
- Long-term equilibrium effects
- General equilibrium adjustments

## Quality Assurance

### Validation Against Official Estimates

Where possible, we validate our baseline estimates against:
- Congressional Budget Office revenue projections
- Joint Committee on Taxation estimates
- Treasury Department analysis
- Social Security Administration actuarial projections

### Sensitivity Testing

We test the robustness of our estimates to:
- Alternative economic assumptions
- Different data weighting approaches  
- Variations in policy implementation details
- Sample composition effects

### Documentation and Reproducibility

All analysis code and parameters are documented to enable:
- Independent verification of results
- Replication by other researchers
- Sensitivity analysis and alternative specifications
- Updates with new data or policy details

The next chapter presents the results of this analytical framework applied to the six Social Security benefit taxation reform options.
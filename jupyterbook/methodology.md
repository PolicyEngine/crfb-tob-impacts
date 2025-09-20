# Methodology

This chapter describes our analytical approach for estimating the budgetary impacts of Social Security benefit taxation reforms. We employ microsimulation modeling using PolicyEngine, an open-source platform that provides detailed estimates of policy changes on federal tax revenue and household-level impacts.

## Microsimulation Framework

### PolicyEngine Platform

Our analysis uses PolicyEngine US, an open-source tax-benefit microsimulation model. PolicyEngine provides several advantages for this analysis:

- **Comprehensive Tax Code Implementation**: Complete modeling of federal income tax provisions, including Social Security benefit taxation rules
- **Policy Flexibility**: Allows detailed specification of complex policy reforms
- **Transparency**: Open-source codebase enables verification and replication
- **Validation**: Regular benchmarking against official government estimates

### Data Foundation

The microsimulation is based on the Enhanced Current Population Survey (CPS) for 2024:

- **Sample Size**: Approximately 20,000 households in the dataset
- **Representative Coverage**: Nationally representative sample weighted to match U.S. population
- **Income Sources**: Detailed information on wages, Social Security benefits, pensions, and other income
- **Demographics**: Age, filing status, state of residence, and other relevant characteristics
- **Enhancement**: Survey data enhanced with statistical matching to capture income and benefit details

## Analysis Implementation

### Code Organization

The analysis is structured in a modular fashion to promote reproducibility and maintainability:

```
src/
├── reforms.py           # Reform definitions for all policy options
├── impact_calculator.py # Microsimulation calculations
└── household_impacts.py # Household-level analysis

scripts/
├── generate_policy_impacts.py    # Main script for fiscal impacts
└── generate_household_impacts.py # Script for household analysis

data/
├── policy_impacts.csv    # Fiscal revenue impacts by year
└── household_impacts.csv # Household impacts by income level
```

### Reform Definitions (`src/reforms.py`)

The reforms module contains reusable functions for each policy option:

- **Modular Components**: Common elements like `zero_ss_tax_thresholds()` and `tax_85_percent_ss()` are defined separately
- **Reform Dictionary**: Maps option IDs to reform functions
- **JCT Convention**: Revenue impacts follow Joint Committee on Taxation convention (positive = revenue gain)

Key functions:
- `eliminate_ss_taxation()`: Sets taxation rates to zero
- `tax_85_percent_ss()`: Implements universal 85% taxation
- `permanent_senior_deduction()`: Extends the $6,000 bonus deduction
- `ss_tax_credit()`: Implements a nonrefundable tax credit
- `roth_style_swap()`: Taxes employer payroll contributions
- `phased_roth_style()`: Gradual transition over multiple years

### Impact Calculation (`src/impact_calculator.py`)

The impact calculator handles the microsimulation computations:

```python
class ImpactCalculator:
    def __init__(self, dataset_path):
        # Initialize with CPS dataset

    def calculate_impact(self, reform, year):
        # Compute revenue impact for a reform-year pair
        # Returns impact in dollars (JCT convention)

    def calculate_household_impact(self, reform, year, household_config):
        # Compute household-specific impacts
        # Uses Simulation class with vectorized "axes"
```

Key features:
- **Baseline Caching**: Pre-computes baseline tax liabilities for efficiency
- **Checkpoint Saving**: Incrementally saves results during long calculations
- **JCT Sign Convention**: Reformed minus baseline (positive = revenue increase)

### Data Generation Scripts

#### Fiscal Impact Generation (`scripts/generate_policy_impacts.py`)

This script calculates the 10-year revenue impacts:

1. **Initialization**: Sets up reforms and years (2026-2035)
2. **Baseline Computation**: Pre-calculates baseline for all years
3. **Reform Calculation**: Iterates through 7 reforms × 10 years = 70 calculations
4. **Checkpoint System**: Saves progress to `policy_impacts.csv` after each calculation
5. **Execution Time**: Approximately 30-40 minutes for full dataset

Output format in `data/policy_impacts.csv`:
```csv
reform_id,reform_name,year,revenue_impact
option1,Full Repeal of Social Security Benefits Taxation,2026,-86300000000.0
```

#### Household Impact Generation (`scripts/generate_household_impacts.py`)

This script analyzes impacts for a representative household:

1. **Household Configuration**: Single 70-year-old with $30,000 Social Security
2. **Income Range**: $0 to $200,000 in employment income ($500 increments)
3. **Vectorized Calculation**: Uses PolicyEngine's "axes" feature for efficiency
4. **Output**: Net income under baseline and reform for visualization

Output format in `data/household_impacts.csv`:
```csv
employment_income,baseline_net_income,reform_net_income,change_in_net_income,reform,year
```

## Calculation Methodology

### Revenue Impact Calculation

For each reform and year, the revenue impact is calculated as:

```python
baseline_sim = Microsimulation(dataset=enhanced_cps)
baseline_tax = baseline_sim.calculate("income_tax", period=year)

reform_sim = Microsimulation(reform=reform, dataset=enhanced_cps)
reform_tax = reform_sim.calculate("income_tax", period=year)

# JCT convention: positive = revenue gain
revenue_impact = reform_tax.sum() - baseline_tax.sum()
```

### Household Impact Calculation

Household impacts use PolicyEngine's vectorized simulation:

```python
sim = Simulation(
    situation={
        "people": {"person": {"age": 70}},
        "axes": [[{"employment_income": {"person": income_range}}]]
    }
)
net_income = sim.calculate("household_net_income", period=year)
```

### Key Methodological Decisions

1. **Static Analysis**: No behavioral responses assumed
2. **Federal Focus**: State tax interactions not modeled
3. **Current Law Baseline**: Includes One Big Beautiful Bill provisions
4. **10-Year Window**: 2026-2035 projection period
5. **Full CPS Dataset**: Uses entire enhanced CPS for representativeness

## Validation and Quality Assurance

### Checkpoint System

The analysis includes automatic checkpointing to prevent data loss:
- Results saved incrementally to CSV
- Ability to resume interrupted calculations
- Progress monitoring during execution

### Testing Infrastructure

- Unit tests for reform definitions
- Validation against known policy scenarios
- Comparison with external estimates where available

### Reproducibility

All code is open source and available for replication:
- Fixed random seeds for sampling
- Versioned dependencies via `uv` package manager
- Documented parameter values and assumptions

## Limitations and Caveats

### Modeling Limitations

- **Static Scoring**: Does not account for behavioral responses
- **Federal Only**: State tax interactions not captured
- **No Dynamic Effects**: Economic growth impacts not modeled
- **Administrative Costs**: Implementation costs not included

### Data Limitations

- **Survey Data**: Subject to reporting errors and non-response
- **Imputation**: Some income sources statistically imputed
- **Point-in-Time**: Based on 2024 CPS data

### Projection Uncertainty

- **Legislative Changes**: Assumes current law except specified reforms
- **Economic Conditions**: Uses CBO economic assumptions
- **Demographics**: Population projections subject to uncertainty

## Summary

This methodology employs state-of-the-art microsimulation techniques to estimate the budgetary impacts of Social Security taxation reforms. The modular code structure, comprehensive documentation, and checkpoint systems ensure reproducibility while the use of PolicyEngine's validated tax calculator provides confidence in the results.
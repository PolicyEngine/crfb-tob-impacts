# Analysis Notebooks

This folder contains notebooks used to **generate data files** for the project. These notebooks are **not part of the published Jupyter Book** and are not executed during CI builds due to their long execution times.

## Notebooks

### `policy-impacts-dynamic.ipynb`
Generates policy impact estimates using three scoring methodologies:
- **Static**: No behavioral responses (2026-2035, 10 years)
- **Dynamic**: With CBO labor supply elasticities, uniform by age (2026 only, ~2 hours)
- **Dynamic with Age Multipliers**: Age-heterogeneous elasticities (2x for 65+, 2026 only, ~2 hours)

**Execution time**: 4-6 hours total for all calculations.

**Output files** (saved to `data/`):
- `policy_impacts_static.csv`
- `policy_impacts_dynamic.csv`
- `policy_impacts_dynamic_multiplier.csv`
- `policy_impacts_comparison.csv`
- `policy_impacts_summary.csv`

**How to run**:
```bash
cd analysis
jupyter nbconvert --to notebook --execute --inplace policy-impacts-dynamic.ipynb
```

**Note**: These data files are committed to the repo, so you don't need to regenerate them unless reforms or parameters change.

### `policy-impacts-2100.ipynb`
Tests all 8 reform options using the 2100 projection dataset to assess long-term impacts.

**Dataset**: `hf://policyengine/test/2100.h5`
**Year**: 2100 only
**Scoring**: Static (no behavioral responses)

**Execution time**: ~20-30 minutes (single year, 8 reforms)

**Output files** (saved to `data/`):
- `policy_impacts_2100.csv` - Full results with all columns
- `policy_impacts_2100_summary.csv` - Summary table sorted by impact

**How to run**:
```bash
cd analysis
jupyter nbconvert --to notebook --execute --inplace policy-impacts-2100.ipynb
```

**Purpose**: Validates that reforms work correctly in long-term projections and provides insight into how demographic/economic changes affect reform impacts.

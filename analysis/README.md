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

"""
Impact calculation functions for policy reforms.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from policyengine_us import Microsimulation, Simulation


def calculate_fiscal_impact(
    reform,
    year: int,
    baseline_income_tax: np.ndarray,
    dataset: Optional[str] = None
) -> float:
    """Calculate the budgetary impact for a given reform and year.

    Args:
        reform: PolicyEngine Reform object
        year: Year to calculate impact for
        baseline_income_tax: Pre-computed baseline income tax array
        dataset: Dataset path for microsimulation (optional)

    Returns:
        Impact in billions (negative = cost, positive = savings)
    """
    try:
        if reform is not None:
            # Handle empty baseline (computation failed)
            if len(baseline_income_tax) == 0:
                print(f"  Warning: Empty baseline for year {year}, skipping")
                return 0.0

            # Create reformed simulation
            if dataset:
                reformed = Microsimulation(reform=reform, dataset=dataset)
            else:
                reformed = Microsimulation(reform=reform)

            reformed_income_tax = reformed.calculate("income_tax", map_to="household", period=year)
            difference_income_tax = baseline_income_tax - reformed_income_tax
            impact_billions = difference_income_tax.sum() / 1e9
        else:
            impact_billions = 0.0

        return round(impact_billions, 1)
    except Exception as e:
        print(f"Error calculating impact for year {year}: {e}")
        return 0.0


def compute_baselines(
    years: List[int],
    dataset: Optional[str] = None
) -> Dict[int, np.ndarray]:
    """Pre-compute baselines for all years to avoid redundant calculations.

    Args:
        years: List of years to compute baselines for
        dataset: Dataset path for microsimulation (optional)

    Returns:
        Dictionary mapping years to baseline income tax arrays
    """
    print("Pre-computing baselines for all years...")
    baselines = {}

    for year in years:
        print(f"  Computing baseline for {year}...")
        try:
            # Try with dataset if provided
            if dataset:
                baseline = Microsimulation(dataset=dataset)
            else:
                # Use default dataset
                baseline = Microsimulation()

            baseline_income_tax = baseline.calculate("income_tax", map_to="household", period=year)
            baselines[year] = baseline_income_tax
        except Exception as e:
            print(f"  Error computing baseline for {year}: {e}")
            print(f"  Using alternative dataset approach...")
            # Try without specifying dataset
            try:
                baseline = Microsimulation()
                baseline_income_tax = baseline.calculate("income_tax", map_to="household", period=year)
                baselines[year] = baseline_income_tax
                print(f"  Successfully computed baseline for {year}")
            except Exception as e2:
                print(f"  Failed to compute baseline for {year}: {e2}")
                # Return empty array as fallback
                baselines[year] = np.array([])

    print("Baseline computation complete!\n")
    return baselines


def calculate_household_impact(
    reform,
    year: int,
    employment_income_range: Tuple[int, int, int] = (0, 200000, 500),
    social_security_benefits: float = 30000,
    age: int = 70,
    state: str = "FL"
) -> pd.DataFrame:
    """Calculate household-level impacts for a reform across income levels.

    Args:
        reform: PolicyEngine Reform object
        year: Year to calculate impact for
        employment_income_range: Tuple of (min, max, step) for employment income
        social_security_benefits: Annual Social Security benefits
        age: Age of the individual
        state: State code

    Returns:
        DataFrame with columns: employment_income, baseline_net_income,
        reform_net_income, change_in_net_income
    """
    min_income, max_income, step = employment_income_range
    income_points = list(range(min_income, max_income + step, step))

    situation = {
        "people": {
            "person1": {
                "age": {str(year): age},
                "social_security_retirement": {str(year): social_security_benefits}
            }
        },
        "families": {
            "your family": {"members": ["person1"]}
        },
        "marital_units": {
            "your marital unit": {"members": ["person1"]}
        },
        "tax_units": {
            "your tax unit": {"members": ["person1"]}
        },
        "spm_units": {
            "your household": {"members": ["person1"]}
        },
        "households": {
            "your household": {
                "members": ["person1"],
                "state_name": {str(year): state}
            }
        },
        "axes": [[
            {
                "name": "employment_income",
                "count": len(income_points),
                "min": min_income,
                "max": max_income
            }
        ]]
    }

    # Calculate reform net income
    simulation_reform = Simulation(reform=reform, situation=situation)
    reform_net_income = simulation_reform.calculate("household_net_income", year)

    # Calculate baseline net income
    simulation_baseline = Simulation(situation=situation)
    baseline_net_income = simulation_baseline.calculate("household_net_income", year)

    # Calculate change
    change_in_net_income = reform_net_income - baseline_net_income

    # Create DataFrame
    df = pd.DataFrame({
        'employment_income': income_points,
        'baseline_net_income': baseline_net_income,
        'reform_net_income': reform_net_income,
        'change_in_net_income': change_in_net_income
    })

    return df


def calculate_multi_year_impacts(
    reform_configs: Dict,
    years: List[int],
    dataset: Optional[str] = None,
    sample_fraction: Optional[float] = None
) -> pd.DataFrame:
    """Calculate impacts for all reforms across multiple years.

    Args:
        reform_configs: Dictionary of reform configurations
        years: List of years to calculate
        dataset: Dataset path (optional)

    Returns:
        DataFrame with all reform impacts
    """
    # Pre-compute baselines
    baselines = compute_baselines(years, dataset)

    all_results = []

    for reform_id, config in reform_configs.items():
        print(f"\nProcessing {config['name']}...")

        if config.get('has_variants', False):
            # Handle reforms with variants
            for variant in config['variants']:
                print(f"  Variant: ${variant}")
                reform = config['func'](variant)

                for year in years:
                    print(f"    Year {year}: Computing...")
                    impact = calculate_fiscal_impact(reform, year, baselines[year], dataset)

                    all_results.append({
                        'reform_id': reform_id,
                        'reform_name': config['name'],
                        'variant_value': variant,
                        'year': year,
                        'impact_billions': impact
                    })
        else:
            # Handle standard reforms
            reform = config['func']()

            for year in years:
                print(f"  Year {year}: Computing...")
                impact = calculate_fiscal_impact(reform, year, baselines[year], dataset)

                all_results.append({
                    'reform_id': reform_id,
                    'reform_name': config['name'],
                    'variant_value': None,
                    'year': year,
                    'impact_billions': impact
                })

    return pd.DataFrame(all_results)
#!/usr/bin/env python
"""
Generate sample data for CI testing.

This creates a minimal dataset for testing the build process.
For production data, use generate_policy_impacts.py.
"""

import pandas as pd
import numpy as np
from pathlib import Path

def main():
    print("Generating sample data for CI...")

    # Create sample fiscal data with realistic structure
    fiscal_data = []
    years = [2026, 2027]  # Just two years for CI

    reforms = [
        ("option1", "Full Repeal of Social Security Benefits Taxation", None),
        ("option2", "Taxation of 85% of Social Security Benefits", None),
        ("option3", "85% Taxation with Permanent Senior Deduction Extension", None),
        ("option4", "Social Security Tax Credit System ($500)", 500),
        ("option5", "Roth-Style Swap", None),
        ("option6", "Phased Roth-Style Swap", None),
        ("option7", "Eliminate Bonus Senior Deduction", None),
    ]

    for reform_id, reform_name, variant in reforms:
        for year in years:
            # Use plausible values based on reform type
            if "Repeal" in reform_name:
                base_impact = 85.0  # Cost
            elif "85%" in reform_name:
                base_impact = -40.0  # Revenue
            elif "Roth" in reform_name:
                base_impact = 10.0  # Small initial impact
            else:
                base_impact = -5.0

            # Add year growth
            year_factor = 1 + (year - 2026) * 0.05
            impact = round(base_impact * year_factor, 1)

            fiscal_data.append({
                'reform_id': reform_id,
                'reform_name': reform_name,
                'variant_value': variant,
                'year': year,
                'impact_billions': impact
            })

    fiscal_df = pd.DataFrame(fiscal_data)

    # Save fiscal impacts
    output_dir = Path('data')
    output_dir.mkdir(exist_ok=True)

    fiscal_output = output_dir / 'policy_impacts.csv'
    fiscal_df.to_csv(fiscal_output, index=False)
    print(f"Fiscal impacts saved to {fiscal_output}")

    # Also save to React dashboard
    dashboard_output = Path('policy-impact-dashboard/public/policy_impacts.csv')
    if dashboard_output.parent.exists():
        fiscal_df.to_csv(dashboard_output, index=False)
        print(f"Also saved to {dashboard_output}")

    # Create minimal household data (just for structure)
    household_data = []
    income_points = [0, 50000, 100000, 150000, 200000]

    for reform_id, reform_name, _ in reforms[:2]:  # Just first two reforms
        for year in [2026]:  # Just one year
            for income in income_points:
                baseline = 40000 + income * 0.75
                if "Repeal" in reform_name:
                    reform_impact = 2000 if income < 100000 else 500
                else:
                    reform_impact = -1000 if income < 100000 else -200

                household_data.append({
                    'reform': reform_name,
                    'year': year,
                    'employment_income': income,
                    'baseline_net_income': baseline,
                    'reform_net_income': baseline + reform_impact,
                    'change_in_net_income': reform_impact
                })

    household_df = pd.DataFrame(household_data)

    # Save household impacts
    household_output = output_dir / 'household_impacts.csv'
    household_df.to_csv(household_output, index=False)
    print(f"Household impacts saved to {household_output}")

    # Also save to Jupyter Book
    jupyterbook_output = Path('jupyterbook/household_impacts_all_years.csv')
    if jupyterbook_output.parent.exists():
        household_df.to_csv(jupyterbook_output, index=False)
        print(f"Also saved to {jupyterbook_output}")

    print(f"\n✓ Generated {len(fiscal_df)} fiscal impact rows")
    print(f"✓ Generated {len(household_df)} household impact rows")
    print("\nSample data generation complete!")

if __name__ == "__main__":
    main()
#!/usr/bin/env python
"""
Generate policy impact data for Social Security taxation reforms.

This script calculates fiscal and household impacts for various policy reforms
and saves the results to CSV files for use in the dashboard and documentation.
"""

import argparse
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.reforms import REFORMS
from src.impact_calculator import calculate_multi_year_impacts, calculate_household_impact
import pandas as pd


def main():
    parser = argparse.ArgumentParser(
        description='Generate policy impact data for Social Security reforms'
    )
    parser.add_argument(
        '--start-year',
        type=int,
        default=2026,
        help='Start year for analysis (default: 2026)'
    )
    parser.add_argument(
        '--end-year',
        type=int,
        default=2035,
        help='End year for analysis (default: 2035)'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default='data',
        help='Output directory for CSV files (default: data)'
    )
    parser.add_argument(
        '--skip-household',
        action='store_true',
        help='Skip household impact calculations'
    )

    args = parser.parse_args()

    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)

    # Generate years list
    years = list(range(args.start_year, args.end_year + 1))
    print(f"Analyzing years {args.start_year} to {args.end_year}")

    # Calculate fiscal impacts
    print("\n" + "=" * 60)
    print("CALCULATING FISCAL IMPACTS")
    print("=" * 60)

    fiscal_impacts = calculate_multi_year_impacts(REFORMS, years)

    # Save fiscal impacts
    fiscal_output = output_dir / 'policy_impacts.csv'
    fiscal_impacts.to_csv(fiscal_output, index=False)
    print(f"\nFiscal impacts saved to {fiscal_output}")

    # Also save to React dashboard location
    dashboard_output = Path('policy-impact-dashboard/public/policy_impacts.csv')
    if dashboard_output.parent.exists():
        fiscal_impacts.to_csv(dashboard_output, index=False)
        print(f"Also saved to {dashboard_output}")

    # Calculate household impacts if not skipped
    if not args.skip_household:
        print("\n" + "=" * 60)
        print("CALCULATING HOUSEHOLD IMPACTS")
        print("=" * 60)

        household_results = []

        for reform_id, config in REFORMS.items():
            print(f"\nProcessing {config['name']}...")

            if config.get('has_variants', False):
                # Use middle variant for household analysis
                variant = config['variants'][len(config['variants']) // 2]
                reform = config['func'](variant)
                reform_name = f"{config['name']} (${variant})"
            else:
                reform = config['func']()
                reform_name = config['name']

            for year in years:
                print(f"  Year {year}...")
                df = calculate_household_impact(reform, year)
                df['reform'] = reform_name
                df['year'] = year
                household_results.append(df)

        # Combine all household results
        household_df = pd.concat(household_results, ignore_index=True)

        # Save household impacts
        household_output = output_dir / 'household_impacts.csv'
        household_df.to_csv(household_output, index=False)
        print(f"\nHousehold impacts saved to {household_output}")

        # Also save to Jupyter Book location
        jupyterbook_output = Path('jupyterbook/household_impacts_all_years.csv')
        if jupyterbook_output.parent.exists():
            household_df.to_csv(jupyterbook_output, index=False)
            print(f"Also saved to {jupyterbook_output}")

    # Print summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"✓ Fiscal impacts: {len(fiscal_impacts)} rows")
    if not args.skip_household:
        print(f"✓ Household impacts: {len(household_df)} rows")
    print(f"✓ Years analyzed: {args.start_year}-{args.end_year}")
    print(f"✓ Reforms processed: {len(REFORMS)}")
    print("\nData generation complete!")


if __name__ == "__main__":
    main()
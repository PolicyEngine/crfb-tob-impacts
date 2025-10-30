"""
Quick Pipeline: Generate Wharton Benchmark Comparison for any dataset

Usage:
    python wharton_comparison_pipeline.py <path_to_h5_file> <year>

Example:
    python wharton_comparison_pipeline.py /Users/ziminghua/Downloads/2054.h5 2054
"""

import sys
import os
import pandas as pd
import numpy as np

# Setup path
repo_root = os.path.abspath('..')
src_path = os.path.join(repo_root, 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from policyengine_us import Microsimulation
from reforms import REFORMS

# Wharton benchmark data (from Excel file)
WHARTON_BENCHMARKS = {
    2026: {
        'First quintile': {'tax_change': 0, 'pct_change': 0.0},
        'Second quintile': {'tax_change': -15, 'pct_change': 0.0},
        'Middle quintile': {'tax_change': -340, 'pct_change': 0.5},
        'Fourth quintile': {'tax_change': -1135, 'pct_change': 1.1},
        '80-90%': {'tax_change': -1625, 'pct_change': 1.0},
        '90-95%': {'tax_change': -1590, 'pct_change': 0.7},
        '95-99%': {'tax_change': -2020, 'pct_change': 0.5},
        '99-99.9%': {'tax_change': -2205, 'pct_change': 0.2},
        'Top 0.1%': {'tax_change': -2450, 'pct_change': 0.0},
    },
    2034: {
        'First quintile': {'tax_change': 0, 'pct_change': 0.0},
        'Second quintile': {'tax_change': -45, 'pct_change': 0.1},
        'Middle quintile': {'tax_change': -615, 'pct_change': 0.8},
        'Fourth quintile': {'tax_change': -1630, 'pct_change': 1.2},
        '80-90%': {'tax_change': -2160, 'pct_change': 1.1},
        '90-95%': {'tax_change': -2160, 'pct_change': 0.7},
        '95-99%': {'tax_change': -2605, 'pct_change': 0.6},
        '99-99.9%': {'tax_change': -2715, 'pct_change': 0.2},
        'Top 0.1%': {'tax_change': -2970, 'pct_change': 0.0},
    },
    2054: {
        'First quintile': {'tax_change': -5, 'pct_change': 0.0},
        'Second quintile': {'tax_change': -275, 'pct_change': 0.3},
        'Middle quintile': {'tax_change': -1730, 'pct_change': 1.3},
        'Fourth quintile': {'tax_change': -3560, 'pct_change': 1.6},
        '80-90%': {'tax_change': -4075, 'pct_change': 1.2},
        '90-95%': {'tax_change': -4385, 'pct_change': 0.9},
        '95-99%': {'tax_change': -4565, 'pct_change': 0.6},
        '99-99.9%': {'tax_change': -4820, 'pct_change': 0.2},
        'Top 0.1%': {'tax_change': -5080, 'pct_change': 0.0},
    },
}

def run_analysis(dataset_path, year):
    """Run Option 1 analysis for given dataset and year"""

    print(f"Loading dataset: {dataset_path}")
    baseline = Microsimulation(dataset=dataset_path)

    option1_reform = REFORMS['option1']['func']()
    reform = Microsimulation(dataset=dataset_path, reform=option1_reform)

    # Get household data
    household_weight = baseline.calculate("household_weight", period=year)
    household_net_income_baseline = baseline.calculate("household_net_income", period=year, map_to="household")
    household_net_income_reform = reform.calculate("household_net_income", period=year, map_to="household")
    income_tax_baseline = baseline.calculate("income_tax", period=year, map_to="household")
    income_tax_reform = reform.calculate("income_tax", period=year, map_to="household")

    # Calculate changes
    tax_change = income_tax_reform - income_tax_baseline
    income_change_pct = ((household_net_income_reform - household_net_income_baseline) / household_net_income_baseline) * 100

    # Create DataFrame
    df = pd.DataFrame({
        'household_net_income': household_net_income_baseline,
        'weight': household_weight,
        'tax_change': tax_change,
        'income_change_pct': income_change_pct,
    })

    # Remove invalid values
    df = df[np.isfinite(df['household_net_income'])]
    df = df[df['household_net_income'] > 0]
    df = df[np.isfinite(df['income_change_pct'])]
    df = df[df['weight'] > 0]

    # Calculate percentiles
    df['income_percentile'] = df['household_net_income'].rank(pct=True) * 100

    # Assign income groups
    def assign_income_group(percentile):
        if percentile <= 20:
            return 'First quintile'
        elif percentile <= 40:
            return 'Second quintile'
        elif percentile <= 60:
            return 'Middle quintile'
        elif percentile <= 80:
            return 'Fourth quintile'
        elif percentile <= 90:
            return '80-90%'
        elif percentile <= 95:
            return '90-95%'
        elif percentile <= 99:
            return '95-99%'
        elif percentile <= 99.9:
            return '99-99.9%'
        else:
            return 'Top 0.1%'

    df['income_group'] = df['income_percentile'].apply(assign_income_group)

    # Calculate aggregate revenue
    revenue_impact = (income_tax_reform.sum() - income_tax_baseline.sum()) / 1e9

    # Calculate by group
    results = []
    for group in ['First quintile', 'Second quintile', 'Middle quintile', 'Fourth quintile',
                  '80-90%', '90-95%', '95-99%', '99-99.9%', 'Top 0.1%']:
        group_data = df[df['income_group'] == group]
        if len(group_data) == 0:
            continue

        total_weight = group_data['weight'].sum()
        avg_tax_change = (group_data['tax_change'] * group_data['weight']).sum() / total_weight
        avg_income_change_pct = (group_data['income_change_pct'] * group_data['weight']).sum() / total_weight

        results.append({
            'group': group,
            'pe_tax_change': round(avg_tax_change),
            'pe_pct_change': round(avg_income_change_pct, 1),
        })

    return pd.DataFrame(results), revenue_impact

def generate_comparison_table(pe_results, year):
    """Generate comparison table with Wharton benchmark"""

    if year not in WHARTON_BENCHMARKS:
        print(f"Warning: No Wharton benchmark available for year {year}")
        return pe_results

    wharton_data = WHARTON_BENCHMARKS[year]

    comparison = []
    for _, row in pe_results.iterrows():
        group = row['group']
        wharton = wharton_data.get(group, {'tax_change': None, 'pct_change': None})

        pe_tax = row['pe_tax_change']
        wh_tax = wharton['tax_change']

        comparison.append({
            'Income Group': group,
            'PolicyEngine': f"${pe_tax:,}",
            'Wharton': f"${wh_tax:,}" if wh_tax is not None else 'N/A',
            'Difference': f"${(pe_tax - wh_tax):,}" if wh_tax is not None else 'N/A',
            'PE %': f"{row['pe_pct_change']}%",
            'Wharton %': f"{wharton['pct_change']}%" if wharton['pct_change'] is not None else 'N/A',
        })

    return pd.DataFrame(comparison)

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)

    dataset_path = sys.argv[1]
    year = int(sys.argv[2])

    print("="*80)
    print(f"WHARTON COMPARISON PIPELINE - YEAR {year}")
    print("="*80)
    print()

    # Run analysis
    print("Running PolicyEngine analysis...")
    pe_results, revenue_impact = run_analysis(dataset_path, year)
    print(f"✓ Analysis complete")
    print(f"  Revenue impact: ${revenue_impact:.1f}B")
    print()

    # Generate comparison table
    print("Generating comparison table...")
    comparison_table = generate_comparison_table(pe_results, year)

    print()
    print("="*80)
    print(f"COMPARISON TABLE: {year}")
    print("="*80)
    print()
    print("Average Tax Change (per household):")
    print(comparison_table[['Income Group', 'PolicyEngine', 'Wharton', 'Difference']].to_string(index=False))
    print()
    print("Percent Change in Income:")
    print(comparison_table[['Income Group', 'PE %', 'Wharton %']].to_string(index=False))
    print()

    # Save to file
    output_file = f"../data/wharton_comparison_{year}.csv"
    comparison_table.to_csv(output_file, index=False)
    print(f"✓ Saved to: {output_file}")
    print()
    print("="*80)

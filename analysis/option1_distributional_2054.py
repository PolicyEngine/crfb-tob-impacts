"""
Calculate distributional impacts of Option 1 (Full Repeal of SS Benefits Taxation) for 2054
to compare with Wharton Budget Model benchmark.

This script calculates:
1. Average tax change by income group
2. Percent change in income after taxes and transfers by income group

Income groups match Wharton benchmark:
- Quintiles (First through Fourth)
- 80-90%, 90-95%, 95-99%, 99-99.9%, Top 0.1%
"""

import sys
import os

# Setup path
repo_root = os.path.abspath('..')
src_path = os.path.join(repo_root, 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

import pandas as pd
import numpy as np
from policyengine_us import Microsimulation
from reforms import REFORMS

print("="*80)
print("DISTRIBUTIONAL ANALYSIS: Option 1 - Year 2054")
print("Full Repeal of Social Security Benefits Taxation")
print("="*80)
print()

# Load baseline and reform simulations
print("Loading 2054 dataset...")
baseline = Microsimulation(dataset="hf://policyengine/test/2054.h5")
option1_reform = REFORMS['option1']['func']()
reform = Microsimulation(dataset="hf://policyengine/test/2054.h5", reform=option1_reform)
print("✓ Simulations loaded")
print()

# Calculate key variables for baseline
print("Calculating baseline values...")
household_weight = baseline.calculate("household_weight", period=2054)
income_tax_baseline = baseline.calculate("income_tax", period=2054, map_to="household")
household_net_income_baseline = baseline.calculate("household_net_income", period=2054, map_to="household")

# Calculate reform values
print("Calculating reform values...")
income_tax_reform = reform.calculate("income_tax", period=2054, map_to="household")
household_net_income_reform = reform.calculate("household_net_income", period=2054, map_to="household")

# Calculate changes
tax_change = income_tax_reform - income_tax_baseline  # Negative = tax cut
# household_net_income already accounts for taxes and transfers
income_change_pct = ((household_net_income_reform - household_net_income_baseline) / household_net_income_baseline) * 100

print("✓ Calculations complete")
print()

# Create DataFrame
df = pd.DataFrame({
    'household_net_income': household_net_income_baseline,
    'weight': household_weight,
    'tax_change': tax_change,
    'income_change_pct': income_change_pct,
    'income_baseline': household_net_income_baseline,
    'income_reform': household_net_income_reform
})

# Remove invalid values
df = df[np.isfinite(df['household_net_income'])]
df = df[df['household_net_income'] > 0]
df = df[np.isfinite(df['income_change_pct'])]

print(f"Analyzing {len(df):,} households (weighted: {df['weight'].sum():,.0f})")
print()

# Calculate income percentiles
df['income_percentile'] = df['household_net_income'].rank(pct=True) * 100

# Define income groups matching Wharton
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

# Calculate weighted averages by group
print("Calculating distributional impacts...")
print()

results = []
group_order = [
    'First quintile', 'Second quintile', 'Middle quintile', 'Fourth quintile',
    '80-90%', '90-95%', '95-99%', '99-99.9%', 'Top 0.1%'
]

for group in group_order:
    group_data = df[df['income_group'] == group]
    if len(group_data) == 0:
        continue

    # Weighted averages
    total_weight = group_data['weight'].sum()
    avg_tax_change = (group_data['tax_change'] * group_data['weight']).sum() / total_weight
    avg_income_change_pct = (group_data['income_change_pct'] * group_data['weight']).sum() / total_weight

    results.append({
        'Income group': group,
        'Average tax change': round(avg_tax_change),
        'Percent change in income, after taxes and transfers': f"{avg_income_change_pct:.1f}%"
    })

results_df = pd.DataFrame(results)

print("="*80)
print("RESULTS: Option 1 Distributional Impacts - 2054")
print("="*80)
print()
print(results_df.to_string(index=False))
print()
print("="*80)

# Save results
output_file = '../data/option1_distributional_2054.csv'
results_df.to_csv(output_file, index=False)
print(f"✓ Results saved to: {output_file}")
print()

print("✓ Analysis complete!")

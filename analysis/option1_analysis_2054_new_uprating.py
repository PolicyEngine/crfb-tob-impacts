"""
Calculate Option 1 impacts for 2054 using NEW dataset with SSA Trustees uprating
This dataset was generated with PR #6744 uprating parameters.
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
print("OPTION 1 ANALYSIS - 2054 (NEW SSA TRUSTEES UPRATING)")
print("Full Repeal of Social Security Benefits Taxation")
print("Dataset: Generated with PR #6744 uprating parameters")
print("="*80)
print()

# Load baseline and reform simulations using new dataset
new_dataset_path = "/Users/ziminghua/Downloads/2054 (1).h5"

print(f"Loading new dataset: {new_dataset_path}")
baseline = Microsimulation(dataset=new_dataset_path)
print("✓ Baseline loaded")

option1_reform = REFORMS['option1']['func']()
reform = Microsimulation(dataset=new_dataset_path, reform=option1_reform)
print("✓ Reform simulation loaded")
print()

# Check dataset size
household_weight = baseline.calculate("household_weight", period=2054)
print(f"Dataset info:")
print(f"  Households in sample: {len(household_weight):,}")
print(f"  Weighted households: {household_weight.sum():,.0f}")
print()

# Calculate aggregate revenue impact
print("="*80)
print("AGGREGATE REVENUE IMPACT (2054)")
print("="*80)
print()

baseline_income_tax = baseline.calculate("income_tax", period=2054, map_to="household")
reform_income_tax = reform.calculate("income_tax", period=2054, map_to="household")

revenue_impact = reform_income_tax.sum() - baseline_income_tax.sum()
revenue_impact_billions = revenue_impact / 1e9

print(f"Baseline income tax: ${baseline_income_tax.sum() / 1e9:,.1f}B")
print(f"Reform income tax:   ${reform_income_tax.sum() / 1e9:,.1f}B")
print(f"Revenue impact:      ${revenue_impact_billions:,.1f}B")
print()

# Calculate distributional impacts
print("="*80)
print("DISTRIBUTIONAL ANALYSIS (2054)")
print("="*80)
print()

# Get household-level data
household_net_income_baseline = baseline.calculate("household_net_income", period=2054, map_to="household")
household_net_income_reform = reform.calculate("household_net_income", period=2054, map_to="household")
income_tax_baseline = baseline.calculate("income_tax", period=2054, map_to="household")
income_tax_reform = reform.calculate("income_tax", period=2054, map_to="household")

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
results = []
group_order = [
    'First quintile', 'Second quintile', 'Middle quintile', 'Fourth quintile',
    '80-90%', '90-95%', '95-99%', '99-99.9%', 'Top 0.1%'
]

for group in group_order:
    group_data = df[df['income_group'] == group]
    if len(group_data) == 0:
        continue

    total_weight = group_data['weight'].sum()
    avg_tax_change = (group_data['tax_change'] * group_data['weight']).sum() / total_weight
    avg_income_change_pct = (group_data['income_change_pct'] * group_data['weight']).sum() / total_weight

    results.append({
        'Income group': group,
        'Average tax change': round(avg_tax_change),
        'Percent change in income': f"{avg_income_change_pct:.1f}%",
        'Sample size': len(group_data),
        'Weighted count': round(total_weight)
    })

results_df = pd.DataFrame(results)

print("RESULTS: Option 1 Distributional Impacts - 2054 (New Uprating)")
print("-" * 80)
print(results_df[['Income group', 'Average tax change', 'Percent change in income']].to_string(index=False))
print()
print("Sample sizes by group:")
for _, row in results_df.iterrows():
    print(f"  {row['Income group']:15s}: {row['Sample size']:>6,} households ({row['Weighted count']:>15,.0f} weighted)")
print()

# Comparison with Wharton
wharton_2054 = {
    'First quintile': -5,
    'Second quintile': -275,
    'Middle quintile': -1730,
    'Fourth quintile': -3560,
    '80-90%': -4075,
    '90-95%': -4385,
    '95-99%': -4565,
    '99-99.9%': -4820,
    'Top 0.1%': -5080
}

print("="*80)
print("COMPARISON WITH WHARTON 2054")
print("="*80)
print()

comparison = []
for _, row in results_df.iterrows():
    group = row['Income group']
    pe_val = row['Average tax change']
    wh_val = wharton_2054[group]
    diff = pe_val - wh_val
    pct_diff = (diff / wh_val * 100) if wh_val != 0 else None

    comparison.append({
        'Income Group': group,
        'PE (New Uprating)': pe_val,
        'Wharton': wh_val,
        'Difference': diff,
        '% Diff': f"{pct_diff:.0f}%" if pct_diff is not None else 'N/A'
    })

comp_df = pd.DataFrame(comparison)
print(comp_df.to_string(index=False))
print()

print("="*80)
print(f"Revenue Impact: ${revenue_impact_billions:.1f}B")
print("Dataset: 2054 (1).h5 - Generated with SSA Trustees uprating (PR #6744)")
print("="*80)

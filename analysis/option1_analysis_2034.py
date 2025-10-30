"""
Calculate Option 1 (Full Repeal of SS Benefits Taxation) impacts for 2034
using enhanced_cps_2024 (reweighted to 2034) for Wharton comparison.
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
print("OPTION 1 ANALYSIS - 2034 (Enhanced CPS 2024 → 2034)")
print("Full Repeal of Social Security Benefits Taxation")
print("="*80)
print()

# Use default dataset (enhanced_cps_2024) and let PolicyEngine reweight to 2034
print("Loading enhanced_cps_2024 (will be reweighted to 2034)...")
baseline = Microsimulation()
option1_reform = REFORMS['option1']['func']()
reform = Microsimulation(reform=option1_reform)
print("✓ Simulations loaded")
print()

# Check dataset size
household_weight = baseline.calculate("household_weight", period=2034)
print(f"Dataset info for 2034:")
print(f"  Households in sample: {len(household_weight):,}")
print(f"  Weighted households: {household_weight.sum():,.0f}")
print()

# Calculate aggregate revenue impact
print("="*80)
print("AGGREGATE REVENUE IMPACT (2034)")
print("="*80)
print()

baseline_income_tax = baseline.calculate("income_tax", period=2034, map_to="household")
reform_income_tax = reform.calculate("income_tax", period=2034, map_to="household")

revenue_impact = reform_income_tax.sum() - baseline_income_tax.sum()
revenue_impact_billions = revenue_impact / 1e9

print(f"Baseline income tax: ${baseline_income_tax.sum() / 1e9:,.1f}B")
print(f"Reform income tax:   ${reform_income_tax.sum() / 1e9:,.1f}B")
print(f"Revenue impact:      ${revenue_impact_billions:,.1f}B")
print()

# Save aggregate result
os.makedirs('../data', exist_ok=True)
agg_df = pd.DataFrame([{
    'reform_id': 'option1',
    'reform_name': 'Full Repeal of Social Security Benefits Taxation',
    'year': 2034,
    'revenue_impact': revenue_impact,
    'revenue_impact_billions': revenue_impact_billions,
    'scoring_type': 'static',
    'dataset': 'enhanced_cps_2024_reweighted_to_2034'
}])
agg_df.to_csv('../data/option1_aggregate_2034.csv', index=False)
print("✓ Saved aggregate results to data/option1_aggregate_2034.csv")
print()

# Calculate distributional impacts
print("="*80)
print("DISTRIBUTIONAL ANALYSIS (2034)")
print("="*80)
print()

# Get household-level data
household_net_income_baseline = baseline.calculate("household_net_income", period=2034, map_to="household")
household_net_income_reform = reform.calculate("household_net_income", period=2034, map_to="household")
income_tax_baseline = baseline.calculate("income_tax", period=2034, map_to="household")
income_tax_reform = reform.calculate("income_tax", period=2034, map_to="household")

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
        'Percent change in income, after taxes and transfers': f"{avg_income_change_pct:.1f}%",
        'Sample size': len(group_data),
        'Weighted count': round(total_weight)
    })

results_df = pd.DataFrame(results)

print("RESULTS: Option 1 Distributional Impacts - 2034")
print("-" * 80)
print(results_df[['Income group', 'Average tax change', 'Percent change in income, after taxes and transfers']].to_string(index=False))
print()
print("Sample sizes by group:")
for _, row in results_df.iterrows():
    print(f"  {row['Income group']:15s}: {row['Sample size']:>6,} households ({row['Weighted count']:>15,.0f} weighted)")
print()

# Save results
results_df.to_csv('../data/option1_distributional_2034.csv', index=False)
print("✓ Saved distributional results to data/option1_distributional_2034.csv")
print()

print("="*80)
print("✓ Analysis complete!")
print("="*80)

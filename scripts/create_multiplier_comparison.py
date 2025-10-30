"""
Create a comparison CSV showing static vs dynamic_multiplier and dynamic vs dynamic_multiplier
"""
import pandas as pd

# Read the input CSVs
comparison_df = pd.read_csv('data/policy_impacts_comparison.csv')
multiplier_df = pd.read_csv('data/policy_impacts_dynamic_multiplier.csv')

# Merge on reform_id and year
merged = comparison_df.merge(
    multiplier_df[['reform_id', 'year', 'revenue_impact']],
    on=['reform_id', 'year'],
    how='inner'
)

# Rename for clarity
merged = merged.rename(columns={'revenue_impact': 'dynamic_multiplier_impact'})

# Calculate differences: static to dynamic (original feedback)
merged['static_to_dynamic_diff'] = merged['dynamic_impact'] - merged['static_impact']
merged['static_to_dynamic_pct'] = (merged['static_to_dynamic_diff'] / merged['static_impact'].abs()) * 100

# Calculate differences: static to dynamic_multiplier
merged['static_to_multiplier_diff'] = merged['dynamic_multiplier_impact'] - merged['static_impact']
merged['static_to_multiplier_pct'] = (merged['static_to_multiplier_diff'] / merged['static_impact'].abs()) * 100

# Calculate differences: dynamic to dynamic_multiplier
merged['dynamic_to_multiplier_diff'] = merged['dynamic_multiplier_impact'] - merged['dynamic_impact']
merged['dynamic_to_multiplier_pct'] = (merged['dynamic_to_multiplier_diff'] / merged['dynamic_impact'].abs()) * 100

# Select and order columns
output_df = merged[[
    'reform_id',
    'reform_name',
    'year',
    'static_impact',
    'dynamic_impact',
    'dynamic_multiplier_impact',
    'static_to_dynamic_diff',
    'static_to_dynamic_pct',
    'static_to_multiplier_diff',
    'static_to_multiplier_pct',
    'dynamic_to_multiplier_diff',
    'dynamic_to_multiplier_pct'
]]

# Save to CSV
output_df.to_csv('data/policy_impacts_multiplier_comparison.csv', index=False)

print("Created: data/policy_impacts_multiplier_comparison.csv")
print(f"\nRows: {len(output_df)}")
print("\nSample of results:")
print(output_df.head())

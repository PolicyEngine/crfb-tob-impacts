#!/usr/bin/env python3
import pandas as pd

# Read the CSV file
df = pd.read_csv('data/policy_impacts.csv')

# Filter for option2
option2_df = df[df['reform_id'] == 'option2']

# Sum up the revenue impacts
total = option2_df['revenue_impact'].sum() / 1e9  # Convert to billions

print(f'Option 2 total over 10 years: ${total:.1f}B')
print('\nBreakdown by year:')
for _, row in option2_df.iterrows():
    impact_b = row['revenue_impact'] / 1e9
    print(f'  {int(row["year"])}: ${impact_b:.1f}B')
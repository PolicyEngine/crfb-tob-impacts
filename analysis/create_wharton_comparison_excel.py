"""
Create Excel spreadsheet with Wharton Budget Model comparison
for all three years (2026, 2034, 2054) using enhanced_cps_2024 dataset
"""

import pandas as pd
import os

# Wharton benchmark data
wharton_2026 = {
    'Income Group': ['First quintile', 'Second quintile', 'Middle quintile', 'Fourth quintile',
                     '80-90%', '90-95%', '95-99%', '99-99.9%', 'Top 0.1%'],
    'Avg Tax Change': [0, -15, -340, -1135, -1625, -1590, -2020, -2205, -2450],
    'Pct Change Income': [0.0, 0.0, 0.5, 1.1, 1.0, 0.7, 0.5, 0.2, 0.0]
}

wharton_2034 = {
    'Income Group': ['First quintile', 'Second quintile', 'Middle quintile', 'Fourth quintile',
                     '80-90%', '90-95%', '95-99%', '99-99.9%', 'Top 0.1%'],
    'Avg Tax Change': [0, -45, -615, -1630, -2160, -2160, -2605, -2715, -2970],
    'Pct Change Income': [0.0, 0.1, 0.8, 1.2, 1.1, 0.7, 0.6, 0.2, 0.0]
}

wharton_2054 = {
    'Income Group': ['First quintile', 'Second quintile', 'Middle quintile', 'Fourth quintile',
                     '80-90%', '90-95%', '95-99%', '99-99.9%', 'Top 0.1%'],
    'Avg Tax Change': [-5, -275, -1730, -3560, -4075, -4385, -4565, -4820, -5080],
    'Pct Change Income': [0.0, 0.3, 1.3, 1.6, 1.2, 0.9, 0.6, 0.2, 0.0]
}

# PolicyEngine results
pe_2026 = {
    'Income Group': ['First quintile', 'Second quintile', 'Middle quintile', 'Fourth quintile',
                     '80-90%', '90-95%', '95-99%', '99-99.9%', 'Top 0.1%'],
    'Avg Tax Change': [-24, -65, -417, -763, -2148, -2907, -1972, -1608, 0],
    'Pct Change Income': [0.1, 0.1, 0.4, 0.5, 1.1, 1.0, 0.5, 0.1, 0.0]
}

pe_2034 = {
    'Income Group': ['First quintile', 'Second quintile', 'Middle quintile', 'Fourth quintile',
                     '80-90%', '90-95%', '95-99%', '99-99.9%', 'Top 0.1%'],
    'Avg Tax Change': [-39, -195, -769, -1291, -3053, -3388, -2325, -2250, 0],
    'Pct Change Income': [0.1, 0.2, 0.7, 0.7, 1.2, 0.9, 0.4, 0.1, 0.0]
}

pe_2054 = {
    'Income Group': ['First quintile', 'Second quintile', 'Middle quintile', 'Fourth quintile',
                     '80-90%', '90-95%', '95-99%', '99-99.9%', 'Top 0.1%'],
    'Avg Tax Change': [-5, -242, -757, -1558, -3518, -5094, -5183, -3231, 0],
    'Pct Change Income': [0.0, 0.3, 0.5, 0.7, 1.2, 1.2, 0.9, 0.2, 0.0]
}

# Create comparison DataFrames
def create_comparison_sheet(pe_data, wharton_data, year):
    """Create comparison sheet for a given year"""
    df = pd.DataFrame({
        'Income Group': pe_data['Income Group'],

        'PolicyEngine - Avg Tax Change ($)': pe_data['Avg Tax Change'],
        'Wharton - Avg Tax Change ($)': wharton_data['Avg Tax Change'],
        'Difference ($)': [pe - wh for pe, wh in zip(pe_data['Avg Tax Change'], wharton_data['Avg Tax Change'])],
        '% Difference': [round((pe - wh) / wh * 100, 1) if wh != 0 else None
                        for pe, wh in zip(pe_data['Avg Tax Change'], wharton_data['Avg Tax Change'])],

        'PolicyEngine - % Change Income': pe_data['Pct Change Income'],
        'Wharton - % Change Income': wharton_data['Pct Change Income'],
        'Difference (pp)': [round(pe - wh, 1) for pe, wh in zip(pe_data['Pct Change Income'], wharton_data['Pct Change Income'])]
    })

    return df

# Create comparison sheets
df_2026 = create_comparison_sheet(pe_2026, wharton_2026, 2026)
df_2034 = create_comparison_sheet(pe_2034, wharton_2034, 2034)
df_2054 = create_comparison_sheet(pe_2054, wharton_2054, 2054)

# Create revenue impact summary
revenue_summary = pd.DataFrame({
    'Year': [2026, 2034, 2054],
    'PolicyEngine Revenue Impact ($B)': [-85.4, -131.7, -176.3],
    'Dataset': ['Enhanced CPS 2024 → 2026', 'Enhanced CPS 2024 → 2034', 'Enhanced CPS 2024 → 2054'],
    'Households (Sample)': [20863, 20874, 20892],
    'Households (Weighted M)': [141.8, 146.4, 150.1]
})

# Create single sheet with all three years
print("Creating Excel file with single sheet...")

output_file = '../data/wharton_comparison_enhanced_cps_2024.xlsx'

# Build combined sheet with all three tables
rows = []

# Add revenue summary at top
rows.append(['AGGREGATE REVENUE IMPACT (Billions)', '', '', '', ''])
rows.append(['Year', 'PolicyEngine (Enhanced CPS 2024)', 'Dataset Info', '', ''])
rows.append([2026, -85.4, '20,863 households, 141.8M weighted', '', ''])
rows.append([2034, -131.7, '20,874 households, 146.4M weighted', '', ''])
rows.append([2054, -176.3, '20,892 households, 150.1M weighted', '', ''])
rows.append(['', '', '', '', ''])

# Year 2026 table
rows.append(['YEAR 2026 COMPARISON', '', '', '', ''])
rows.append(['Income Group', 'PolicyEngine ($)', 'Wharton ($)', 'Difference ($)', 'PE % Change'])
for i in range(len(df_2026)):
    rows.append([
        df_2026.iloc[i]['Income Group'],
        df_2026.iloc[i]['PolicyEngine - Avg Tax Change ($)'],
        df_2026.iloc[i]['Wharton - Avg Tax Change ($)'],
        df_2026.iloc[i]['Difference ($)'],
        df_2026.iloc[i]['PolicyEngine - % Change Income']
    ])
rows.append(['', '', '', '', ''])

# Year 2034 table
rows.append(['YEAR 2034 COMPARISON', '', '', '', ''])
rows.append(['Income Group', 'PolicyEngine ($)', 'Wharton ($)', 'Difference ($)', 'PE % Change'])
for i in range(len(df_2034)):
    rows.append([
        df_2034.iloc[i]['Income Group'],
        df_2034.iloc[i]['PolicyEngine - Avg Tax Change ($)'],
        df_2034.iloc[i]['Wharton - Avg Tax Change ($)'],
        df_2034.iloc[i]['Difference ($)'],
        df_2034.iloc[i]['PolicyEngine - % Change Income']
    ])
rows.append(['', '', '', '', ''])

# Year 2054 table
rows.append(['YEAR 2054 COMPARISON', '', '', '', ''])
rows.append(['Income Group', 'PolicyEngine ($)', 'Wharton ($)', 'Difference ($)', 'PE % Change'])
for i in range(len(df_2054)):
    rows.append([
        df_2054.iloc[i]['Income Group'],
        df_2054.iloc[i]['PolicyEngine - Avg Tax Change ($)'],
        df_2054.iloc[i]['Wharton - Avg Tax Change ($)'],
        df_2054.iloc[i]['Difference ($)'],
        df_2054.iloc[i]['PolicyEngine - % Change Income']
    ])

# Create single DataFrame
final_df = pd.DataFrame(rows)

# Write to Excel
with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
    final_df.to_excel(writer, sheet_name='Wharton Comparison', index=False, header=False)

print(f"✓ Excel file created: {output_file}")
print()
print("Single sheet with:")
print("  - Revenue summary table (2026, 2034, 2054)")
print("  - 2026 comparison table")
print("  - 2034 comparison table")
print("  - 2054 comparison table")
print()
print("Dataset used: Enhanced CPS 2024 (reweighted to each target year)")
print()
print("✓ Complete!")

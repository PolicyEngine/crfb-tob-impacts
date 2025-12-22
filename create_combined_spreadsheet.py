"""
Create a combined spreadsheet with all reform data for both static and dynamic scoring.
Uses the same allocation logic as dataLoader.ts in the dashboard.
"""
import pandas as pd

# Load economic projections
econ = pd.read_csv('dashboard/public/data/ssa_economic_projections.csv')
econ_dict = {row['year']: row for _, row in econ.iterrows()}

# Load static and dynamic results
static_df = pd.read_csv('dashboard/public/data/all_static_results.csv')
dynamic_df = pd.read_csv('dashboard/public/data/all_dynamic_results.csv')

# Combine both
combined = pd.concat([static_df, dynamic_df], ignore_index=True)

# Process each row
rows = []
for _, row in combined.iterrows():
    reform = row['reform_name']
    year = row['year']
    scoring_type = row['scoring_type']

    # Different options use different columns for impacts (matches dataLoader.ts)
    if reform == 'option7':
        # Option 7: Revenue goes to general revenues, not trust funds
        revenue_impact = row['revenue_impact']
        oasdi_impact = 0
        hi_impact = 0
    elif reform in ['option3', 'option4']:
        # Options 3-4: Allocate full revenue_impact to trust funds based on baseline shares
        revenue_impact = row['revenue_impact']
        baseline_oasdi = row['baseline_tob_oasdi']
        baseline_hi = row['baseline_tob_medicare_hi']
        baseline_total = baseline_oasdi + baseline_hi

        if baseline_total > 0:
            oasdi_share = baseline_oasdi / baseline_total
            hi_share = baseline_hi / baseline_total
            oasdi_impact = revenue_impact * oasdi_share
            hi_impact = revenue_impact * hi_share
        else:
            oasdi_impact = 0
            hi_impact = 0
    elif reform in ['option5', 'option6']:
        # Options 5-6: use oasdi_net_impact and hi_net_impact
        oasdi_impact = row['oasdi_net_impact']
        hi_impact = row['hi_net_impact']
        revenue_impact = oasdi_impact + hi_impact
    else:
        # Options 1-2, 8: use tob_oasdi_impact and tob_medicare_hi_impact
        oasdi_impact = row['tob_oasdi_impact']
        hi_impact = row['tob_medicare_hi_impact']
        revenue_impact = oasdi_impact + hi_impact

    # Get economic data for this year
    econ_row = econ_dict.get(year, {'taxable_payroll': 0, 'gdp': 0})
    taxable_payroll = econ_row['taxable_payroll']
    gdp = econ_row['gdp']

    # Calculate percentages
    pct_payroll = (revenue_impact / taxable_payroll * 100) if taxable_payroll > 0 else 0
    pct_gdp = (revenue_impact / gdp * 100) if gdp > 0 else 0
    oasdi_pct_payroll = (oasdi_impact / taxable_payroll * 100) if taxable_payroll > 0 else 0
    hi_pct_payroll = (hi_impact / taxable_payroll * 100) if taxable_payroll > 0 else 0
    oasdi_pct_gdp = (oasdi_impact / gdp * 100) if gdp > 0 else 0
    hi_pct_gdp = (hi_impact / gdp * 100) if gdp > 0 else 0

    rows.append({
        'Reform': reform,
        'Year': year,
        'Revenue impact (B)': round(revenue_impact, 2),
        'OASDI revenue impact (B)': round(oasdi_impact, 2),
        'HI revenue impact (B)': round(hi_impact, 2),
        'Type': scoring_type,
        'OASDI taxable payroll (B)': round(taxable_payroll, 2),
        'GDP (B)': round(gdp, 2),
        '% of OASDI taxable payroll': round(pct_payroll, 4),
        '% of GDP': round(pct_gdp, 4),
        'OASDI % of OASDI taxable payroll': round(oasdi_pct_payroll, 4),
        'HI % of OASDI taxable payroll': round(hi_pct_payroll, 4),
        'OASDI % of GDP': round(oasdi_pct_gdp, 4),
        'HI % of GDP': round(hi_pct_gdp, 4),
    })

# Create DataFrame and save
result_df = pd.DataFrame(rows)
result_df = result_df.sort_values(['Reform', 'Type', 'Year'])
result_df.to_csv('dashboard_data_combined.csv', index=False)

print(f"Created dashboard_data_combined.csv with {len(result_df)} rows")
print(f"\nColumns: {list(result_df.columns)}")
print(f"\nReforms: {sorted(result_df['Reform'].unique())}")
print(f"Types: {result_df['Type'].unique()}")
print(f"Years: {result_df['Year'].min()} - {result_df['Year'].max()}")

# Show sample rows
print("\n--- Sample: Option 3, Static, 2029 (shows baseline allocation) ---")
sample = result_df[(result_df['Reform'] == 'option3') & (result_df['Type'] == 'static') & (result_df['Year'] == 2029)]
print(sample.to_string(index=False))

print("\n--- Sample: Option 7, Static, 2026 (shows general revenue allocation) ---")
sample = result_df[(result_df['Reform'] == 'option7') & (result_df['Type'] == 'static') & (result_df['Year'] == 2026)]
print(sample.to_string(index=False))

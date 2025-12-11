"""
Allocate revenue impacts to Medicare HI and OASDI trust funds based on baseline ratios.

This script takes impacts.csv and allocates the total revenue_impact to Medicare and OASDI
using the baseline ratio for each respective year. For example, if in 2026 the baseline
Medicare revenues are 80% and OASDI is 20%, and the total revenue impact is -$100B,
then Medicare gets -$80B and OASDI gets -$20B.

Input: impacts.csv (tab-separated)
Output: impacts_trust_breakdown.csv (comma-separated)
"""

import pandas as pd


def allocate_trust_breakdown(input_file: str, output_file: str, options: list[str] | None = None):
    """
    Allocate revenue impacts to trust funds based on baseline ratios.

    Args:
        input_file: Path to input CSV (tab-separated)
        output_file: Path to output CSV
        options: List of reform options to include (e.g., ['option1', 'option2', 'option4', 'option8'])
                 If None, includes all options.
    """
    # Read the impacts file (tab-separated)
    df = pd.read_csv(input_file, sep='\t')

    # Filter to specified options if provided
    if options:
        df = df[df['reform_name'].isin(options)].copy()
    else:
        df = df.copy()

    # Calculate baseline ratios for Medicare and OASDI
    df['baseline_medicare_ratio'] = df['baseline_tob_medicare_hi'] / df['baseline_tob_total']
    df['baseline_oasdi_ratio'] = df['baseline_tob_oasdi'] / df['baseline_tob_total']

    # Allocate revenue_impact based on baseline ratios
    df['revenue_impact_medicare'] = (df['revenue_impact'] * df['baseline_medicare_ratio']).round(2)
    df['revenue_impact_oasdi'] = (df['revenue_impact'] * df['baseline_oasdi_ratio']).round(2)

    # Update Medicare HI columns: impact = allocated, reform = baseline + impact
    df['tob_medicare_hi_impact'] = df['revenue_impact_medicare']
    df['reform_tob_medicare_hi'] = df['baseline_tob_medicare_hi'] + df['tob_medicare_hi_impact']

    # Update OASDI columns: impact = allocated, reform = baseline + impact
    df['tob_oasdi_impact'] = df['revenue_impact_oasdi']
    df['reform_tob_oasdi'] = df['baseline_tob_oasdi'] + df['tob_oasdi_impact']

    # Update reform_tob_total based on new allocated impacts
    # tob_total_impact is kept as the sum of allocated Medicare + OASDI impacts
    df['tob_total_impact'] = df['tob_medicare_hi_impact'] + df['tob_oasdi_impact']
    df['reform_tob_total'] = df['baseline_tob_total'] + df['tob_total_impact']

    # Select exactly the same columns as original impacts.csv
    output_df = df[[
        'reform_name',
        'year',
        'baseline_revenue',
        'reform_revenue',
        'revenue_impact',
        'baseline_tob_medicare_hi',
        'reform_tob_medicare_hi',
        'tob_medicare_hi_impact',
        'baseline_tob_oasdi',
        'reform_tob_oasdi',
        'tob_oasdi_impact',
        'baseline_tob_total',
        'reform_tob_total',
        'tob_total_impact',
        'scoring_type'
    ]].copy()

    # Round numeric columns
    numeric_cols = output_df.columns.drop(['reform_name', 'scoring_type'])
    output_df[numeric_cols] = output_df[numeric_cols].round(2)

    # Save to CSV
    output_df.to_csv(output_file, index=False)

    return output_df


if __name__ == '__main__':
    # Allocate for options 1, 2, 4, and 8
    options_to_include = ['option1', 'option2', 'option4', 'option8']

    df = allocate_trust_breakdown(
        input_file='impacts.csv',
        output_file='impacts_trust_breakdown.csv',
        options=options_to_include
    )

    print(f"Created impacts_trust_breakdown.csv with {len(df)} rows")
    print(f"Options included: {df['reform_name'].unique().tolist()}")
    print(f"Years: {df['year'].min()} - {df['year'].max()}")
    print(f"\nSample output (first 3 rows):")
    print(df.head(3).to_string())

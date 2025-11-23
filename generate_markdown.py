"""
Generate markdown files from templates by populating with data from CSV.

This script reads revenue impact data and populates Jinja2 templates with
calculated values, ensuring all numbers in the documentation stay synchronized
with the underlying data.
"""

import pandas as pd
from jinja2 import Template
from pathlib import Path


def load_revenue_data():
    """Load and process revenue impacts CSV."""
    df = pd.read_csv('data/revenue_impacts.csv')
    return df


def calculate_10year_totals(df):
    """Calculate 10-year totals (2026-2035) for each reform option."""
    # Filter for 10-year window and static scoring
    df_10yr = df[(df['year'].between(2026, 2035)) & (df['scoring_type'] == 'static')]

    # Sum by reform
    totals = df_10yr.groupby('reform_name')['revenue_impact'].sum()

    return totals


def format_billions(value, decimals=0):
    """Format a number as billions, rounded to specified decimals."""
    if decimals == 0:
        return f"{value:,.0f}"
    else:
        return f"{value:,.{decimals}f}"


def format_trillions(value, decimals=1):
    """Format a number as trillions with specified decimals."""
    trillions = value / 1000
    return f"{trillions:,.{decimals}f}"


def generate_external_estimates():
    """Generate external-estimates.md from template."""

    # Load data
    df = load_revenue_data()
    totals = calculate_10year_totals(df)

    # Prepare template variables (all in billions, rounded to nearest billion)
    variables = {
        'opt1_10yr': format_billions(totals['option1']),
        'opt2_10yr': format_billions(totals['option2']),
        'opt3_10yr': format_billions(totals['option3']),
        'opt4_10yr': format_billions(totals['option4']),
        'opt5_10yr': format_billions(totals['option5']),
        'opt6_10yr': format_billions(totals['option6']),
        'opt7_10yr': format_billions(totals['option7']),
        'opt8_10yr': format_billions(totals['option8']),

        # Special formatting for Option 1 in trillions with sign
        'opt1_10yr_with_sign': format_trillions(totals['option1'], decimals=1),
    }

    # Load template
    template_path = Path('jupyterbook/templates/external-estimates.md.tpl')
    with open(template_path) as f:
        template = Template(f.read())

    # Render template
    output = template.render(**variables)

    # Write output
    output_path = Path('jupyterbook/external-estimates.md')
    with open(output_path, 'w') as f:
        f.write(output)

    print(f"✓ Generated {output_path}")
    print("\nPopulated values:")
    for key, value in sorted(variables.items()):
        print(f"  {key}: {value}")


if __name__ == '__main__':
    generate_external_estimates()
    print("\n✓ All markdown files generated successfully")

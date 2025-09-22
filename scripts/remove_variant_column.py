#!/usr/bin/env python3
"""Remove variant_value column from policy impacts CSV."""

import pandas as pd
import os

def remove_variant_column():
    """Remove variant_value column from policy_impacts.csv"""

    csv_path = "data/policy_impacts.csv"

    if not os.path.exists(csv_path):
        print(f"File {csv_path} not found")
        return

    # Read CSV
    df = pd.read_csv(csv_path)

    # Check if variant_value column exists
    if 'variant_value' in df.columns:
        print(f"Removing variant_value column from {csv_path}")
        df = df.drop('variant_value', axis=1)

        # Save back
        df.to_csv(csv_path, index=False)
        print(f"✓ Updated {csv_path} - removed variant_value column")
        print(f"  Remaining columns: {', '.join(df.columns)}")
    else:
        print(f"variant_value column not found in {csv_path}")
        print(f"  Current columns: {', '.join(df.columns)}")

if __name__ == "__main__":
    remove_variant_column()
#!/usr/bin/env python
"""Update the simulation version documentation from metadata."""

import json
from pathlib import Path


def update_version_docs():
    """Update simulation-version.md from simulation_metadata.json."""

    # Read metadata
    metadata_file = Path('data/simulation_metadata.json')
    if not metadata_file.exists():
        print(f"Warning: {metadata_file} not found")
        return

    with open(metadata_file) as f:
        metadata = json.load(f)

    # Create version documentation
    version_content = f"""### PolicyEngine US Version

This analysis was conducted using **PolicyEngine US version {metadata['policyengine_us_version']}**.

The simulation was last run on **{metadata['simulation_date']}** using Python {metadata['python_version']}.

Analysis period: **{metadata['analysis_period']}**
"""

    # Write to Jupyter Book
    version_file = Path('jupyterbook/simulation-version.md')
    with open(version_file, 'w') as f:
        f.write(version_content)

    print(f"Updated {version_file}")
    print(f"  PolicyEngine US: {metadata['policyengine_us_version']}")
    print(f"  Simulation date: {metadata['simulation_date']}")


if __name__ == '__main__':
    update_version_docs()
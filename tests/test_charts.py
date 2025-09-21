#!/usr/bin/env python
"""Test that notebooks have been executed and contain chart outputs."""

import json
import sys
import os
import pytest

def check_notebook_outputs(notebook_path):
    """Check if a notebook has executed cells with outputs."""
    with open(notebook_path, 'r') as f:
        nb = json.load(f)

    # Count cells with outputs
    cells_with_outputs = 0
    plotly_outputs = 0

    for cell in nb['cells']:
        if cell.get('cell_type') == 'code':
            outputs = cell.get('outputs', [])
            if outputs:
                cells_with_outputs += 1
                # Check for plotly outputs
                for output in outputs:
                    if output.get('data', {}).get('application/vnd.plotly.v1+json'):
                        plotly_outputs += 1

    return cells_with_outputs, plotly_outputs

@pytest.mark.skipif(not os.path.exists('jupyterbook/revenue-impacts.ipynb'),
                    reason="Notebook not found")
def test_revenue_impacts_notebook_has_outputs():
    """Test that revenue-impacts notebook has chart outputs."""
    cells_with_outputs, plotly_outputs = check_notebook_outputs('jupyterbook/revenue-impacts.ipynb')
    assert plotly_outputs > 0, "Revenue impacts notebook needs to be executed with charts"

@pytest.mark.skipif(not os.path.exists('jupyterbook/household-impacts.ipynb'),
                    reason="Notebook not found")
def test_household_impacts_notebook_has_outputs():
    """Test that household-impacts notebook has chart outputs."""
    cells_with_outputs, plotly_outputs = check_notebook_outputs('jupyterbook/household-impacts.ipynb')
    assert plotly_outputs > 0, "Household impacts notebook needs to be executed with charts"

def main():
    notebooks = [
        'jupyterbook/revenue-impacts.ipynb',
        'jupyterbook/household-impacts.ipynb'
    ]

    all_good = True

    for nb_path in notebooks:
        if os.path.exists(nb_path):
            cells_with_outputs, plotly_outputs = test_notebook_has_outputs(nb_path)

            print(f"\n{nb_path}:")
            print(f"  Cells with outputs: {cells_with_outputs}")
            print(f"  Plotly charts: {plotly_outputs}")

            if plotly_outputs == 0:
                print(f"  ❌ NO CHARTS FOUND - Notebook needs to be executed!")
                all_good = False
            else:
                print(f"  ✓ Charts found")
        else:
            print(f"\n{nb_path}: File not found")
            all_good = False

    if not all_good:
        print("\n❌ FAIL: Some notebooks are missing chart outputs")
        sys.exit(1)
    else:
        print("\n✓ PASS: All notebooks have chart outputs")
        sys.exit(0)

if __name__ == "__main__":
    main()
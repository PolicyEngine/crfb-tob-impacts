#!/usr/bin/env python
"""
Quick integration test to verify PolicyEngine works correctly.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from src.reforms import REFORMS, get_option1_reform
from src.impact_calculator import calculate_fiscal_impact
from policyengine_us import Microsimulation
import numpy as np

def test_basic_functionality():
    """Test that we can create reforms and run simulations."""

    print("Testing basic PolicyEngine functionality...")

    # Test 1: Can we create all reforms?
    print("\n1. Testing reform creation:")
    for reform_id, config in REFORMS.items():
        try:
            if config.get('has_variants'):
                reform = config['func'](500)  # Test with middle value
            else:
                reform = config['func']()
            print(f"   ✓ {config['name']}")
        except Exception as e:
            print(f"   ✗ {config['name']}: {e}")
            return False

    # Test 2: Can we run a basic simulation?
    print("\n2. Testing Microsimulation:")
    try:
        reform = get_option1_reform()
        baseline = Microsimulation()
        reformed = Microsimulation(reform=reform)

        # Just check we can calculate something
        baseline_tax = baseline.calculate("income_tax", period=2026)
        reformed_tax = reformed.calculate("income_tax", period=2026)

        print(f"   ✓ Baseline computed {len(baseline_tax)} households")
        print(f"   ✓ Reformed computed {len(reformed_tax)} households")

        # Calculate a simple impact
        diff = (baseline_tax - reformed_tax).sum() / 1e9
        print(f"   ✓ Impact: ${diff:.1f}B")

    except Exception as e:
        print(f"   ✗ Simulation failed: {e}")
        return False

    # Test 3: Can we use the impact calculator?
    print("\n3. Testing impact calculator:")
    try:
        impact = calculate_fiscal_impact(
            reform=reform,
            year=2026,
            baseline_income_tax=baseline_tax
        )
        print(f"   ✓ Impact calculator returned: ${impact}B")
    except Exception as e:
        print(f"   ✗ Impact calculator failed: {e}")
        return False

    print("\n✅ All integration tests passed!")
    return True


if __name__ == "__main__":
    success = test_basic_functionality()
    sys.exit(0 if success else 1)
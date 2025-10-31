"""
Run Option 1 with enhanced_cps_2024 for year 2026
(Don't commit this - just for testing)
"""

import sys
import os

# Setup path
repo_root = os.path.abspath('..')
src_path = os.path.join(repo_root, 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from policyengine_us import Microsimulation
from reforms import REFORMS

print("="*80)
print("OPTION 1 - YEAR 2026 (Enhanced CPS 2024)")
print("="*80)
print()

print("Loading enhanced_cps_2024...")
baseline = Microsimulation()  # Uses enhanced_cps_2024 by default
option1_reform = REFORMS['option1']['func']()
reform = Microsimulation(reform=option1_reform)
print("✓ Simulations loaded")
print()

# Calculate for year 2026
print("Calculating revenue impact for year 2026...")
baseline_income_tax = baseline.calculate("income_tax", period=2026, map_to="household")
reform_income_tax = reform.calculate("income_tax", period=2026, map_to="household")

revenue_impact = reform_income_tax.sum() - baseline_income_tax.sum()
revenue_impact_billions = revenue_impact / 1e9

print()
print("="*80)
print("RESULTS")
print("="*80)
print(f"Baseline income tax (2026): ${baseline_income_tax.sum() / 1e9:,.1f}B")
print(f"Reform income tax (2026):   ${reform_income_tax.sum() / 1e9:,.1f}B")
print(f"Revenue impact:             ${revenue_impact_billions:,.1f}B")
print()
print("Dataset: Enhanced CPS 2024")
print("="*80)

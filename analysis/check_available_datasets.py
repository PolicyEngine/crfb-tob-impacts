"""
Check available PolicyEngine US datasets
"""

import sys
import os

# Setup path
repo_root = os.path.abspath('..')
src_path = os.path.join(repo_root, 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from policyengine_us import Microsimulation

print("="*80)
print("AVAILABLE POLICYENGINE US DATASETS")
print("="*80)
print()

# Try to get dataset list
try:
    datasets = list(Microsimulation.datasets.keys())
    print(f"Total datasets available: {len(datasets)}")
    print()

    # Group by type
    enhanced_cps = [d for d in datasets if 'enhanced_cps' in d]
    cps = [d for d in datasets if d.startswith('cps_') and 'enhanced' not in d]
    test = [d for d in datasets if 'test' in d or 'hf://' in d]
    other = [d for d in datasets if d not in enhanced_cps + cps + test]

    print("Enhanced CPS datasets (recommended):")
    for d in sorted(enhanced_cps):
        print(f"  - {d}")

    print()
    print("Raw CPS datasets:")
    for d in sorted(cps):
        print(f"  - {d}")

    if test:
        print()
        print("Test/Projection datasets:")
        for d in sorted(test):
            print(f"  - {d}")

    if other:
        print()
        print("Other datasets:")
        for d in sorted(other):
            print(f"  - {d}")

except Exception as e:
    print(f"Could not retrieve dataset list: {e}")
    print()
    print("Common datasets you can try:")
    print("  - enhanced_cps_2026")
    print("  - enhanced_cps_2027")
    print("  - enhanced_cps_2028")
    print("  - enhanced_cps_2029")
    print("  - enhanced_cps_2030")
    print("  - enhanced_cps_2031")
    print("  - enhanced_cps_2032")
    print("  - enhanced_cps_2033")
    print("  - enhanced_cps_2034")

print()
print("="*80)
print()

# Test loading enhanced_cps_2034
print("Testing enhanced_cps_2034...")
try:
    sim = Microsimulation(dataset="enhanced_cps_2034")
    hh_weight = sim.calculate("household_weight", period=2034)
    print(f"✓ enhanced_cps_2034 loaded successfully!")
    print(f"  Households: {len(hh_weight):,}")
    print(f"  Weighted: {hh_weight.sum():,.0f}")
except Exception as e:
    print(f"✗ Could not load enhanced_cps_2034: {e}")

print()
print("✓ Check complete!")

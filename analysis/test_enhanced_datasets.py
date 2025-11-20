"""
Test loading enhanced CPS datasets for 2026, 2034, and other years
"""

from policyengine_us import Microsimulation
import traceback

datasets_to_test = [
    "enhanced_cps_2026",
    "enhanced_cps_2027",
    "enhanced_cps_2028",
    "enhanced_cps_2029",
    "enhanced_cps_2030",
    "enhanced_cps_2031",
    "enhanced_cps_2032",
    "enhanced_cps_2033",
    "enhanced_cps_2034",
]

print("Testing enhanced CPS datasets...")
print("="*80)

working_datasets = []
failed_datasets = []

for dataset_name in datasets_to_test:
    year = int(dataset_name.split('_')[-1])
    print(f"\nTesting {dataset_name}...")

    try:
        # Try to create simulation with this dataset
        sim = Microsimulation(dataset=dataset_name)

        # Try to calculate something to verify it works
        hh_weight = sim.calculate("household_weight", period=year)

        print(f"  ✓ SUCCESS!")
        print(f"    Households: {len(hh_weight):,}")
        print(f"    Weighted: {hh_weight.sum():,.0f}")
        working_datasets.append(dataset_name)

    except Exception as e:
        print(f"  ✗ FAILED: {type(e).__name__}: {e}")
        failed_datasets.append(dataset_name)

print()
print("="*80)
print("SUMMARY")
print("="*80)
print(f"Working datasets: {len(working_datasets)}")
for ds in working_datasets:
    print(f"  ✓ {ds}")

print()
print(f"Failed datasets: {len(failed_datasets)}")
for ds in failed_datasets:
    print(f"  ✗ {ds}")

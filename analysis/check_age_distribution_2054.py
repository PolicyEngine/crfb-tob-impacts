"""
Check age distribution in the 2054 dataset
"""

import sys
import os

# Setup path
repo_root = os.path.abspath('..')
src_path = os.path.join(repo_root, 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

import pandas as pd
import numpy as np
from policyengine_us import Microsimulation

print("="*80)
print("AGE DISTRIBUTION ANALYSIS - 2054 Dataset")
print("="*80)
print()

# Load the 2054 dataset
print("Loading 2054 dataset...")
sim = Microsimulation(dataset="hf://policyengine/test/2054.h5")
print("✓ Dataset loaded")
print()

# Get age and person weight
age = sim.calculate("age", period=2054)

# Get person weight - need to check if this variable exists
try:
    person_weight = sim.calculate("person_weight", period=2054)
except:
    # If person_weight doesn't exist, use household_weight mapped to persons
    print("Note: Using household weight mapped to persons")
    person_weight = sim.calculate("household_weight", period=2054, map_to="person")

# Filter valid ages and weights
valid = (age > 0) & (person_weight > 0) & np.isfinite(age) & np.isfinite(person_weight)
age = age[valid]
person_weight = person_weight[valid]

print(f"Total people in sample: {len(age):,}")
print(f"Total weighted population: {person_weight.sum():,.0f}")
print()

# Calculate age statistics
print("Age Distribution:")
print("-" * 60)

# Age groups
age_groups = [
    ("Under 18", 0, 17),
    ("18-24", 18, 24),
    ("25-34", 25, 34),
    ("35-44", 35, 44),
    ("45-54", 45, 54),
    ("55-64", 55, 64),
    ("65-74", 65, 74),
    ("75-84", 75, 84),
    ("85+", 85, 150)
]

for group_name, min_age, max_age in age_groups:
    mask = (age >= min_age) & (age <= max_age)
    count = mask.sum()
    weighted = person_weight[mask].sum()
    pct = (weighted / person_weight.sum()) * 100
    print(f"{group_name:12s}: {count:>8,} people ({weighted:>15,.0f} weighted, {pct:>5.1f}%)")

print()
print("="*60)

# People over 65
over_65 = age >= 65
count_over_65 = over_65.sum()
weighted_over_65 = person_weight[over_65].sum()
pct_over_65 = (weighted_over_65 / person_weight.sum()) * 100

print(f"People aged 65+:")
print(f"  Sample count: {count_over_65:,}")
print(f"  Weighted count: {weighted_over_65:,.0f}")
print(f"  Percentage of population: {pct_over_65:.1f}%")

print()
print("✓ Analysis complete!")

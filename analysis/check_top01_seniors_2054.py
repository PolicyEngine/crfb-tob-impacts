"""
Check how many seniors (65+) are in the top 0.1% income group in 2054 dataset
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
print("TOP 0.1% SENIORS ANALYSIS - 2054 Dataset")
print("="*80)
print()

# Load the 2054 dataset
print("Loading 2054 dataset...")
sim = Microsimulation(dataset="hf://policyengine/test/2054.h5")
print("✓ Dataset loaded")
print()

# Get household-level data
household_weight = sim.calculate("household_weight", period=2054)
household_net_income = sim.calculate("household_net_income", period=2054, map_to="household")

# Get person-level data
age = sim.calculate("age", period=2054)
person_id = sim.calculate("person_id", period=2054)
household_id = sim.calculate("household_id", period=2054)

# Get Social Security data
ss_benefits = sim.calculate("social_security", period=2054, map_to="household")
taxable_ss_benefits = sim.calculate("taxable_social_security", period=2054, map_to="household")

print("Dataset Statistics:")
print(f"  Total households: {len(household_weight):,}")
print(f"  Total people: {len(age):,}")
print()

# Create household DataFrame
df_hh = pd.DataFrame({
    'household_id': range(len(household_weight)),
    'household_net_income': household_net_income,
    'weight': household_weight,
    'ss_benefits': ss_benefits,
    'taxable_ss_benefits': taxable_ss_benefits
})

# Remove invalid households
df_hh = df_hh[np.isfinite(df_hh['household_net_income'])]
df_hh = df_hh[df_hh['household_net_income'] > 0]
df_hh = df_hh[df_hh['weight'] > 0]

# Calculate income percentile
df_hh['income_percentile'] = df_hh['household_net_income'].rank(pct=True) * 100

# Identify top 0.1%
df_hh['is_top_01'] = df_hh['income_percentile'] > 99.9

# Create person DataFrame
df_person = pd.DataFrame({
    'person_id': person_id,
    'household_id': household_id,
    'age': age
})

# Filter valid ages
df_person = df_person[np.isfinite(df_person['age'])]
df_person = df_person[df_person['age'] > 0]

# Identify seniors
df_person['is_senior'] = df_person['age'] >= 65

# Count seniors per household
seniors_per_hh = df_person[df_person['is_senior']].groupby('household_id').size()
df_hh['num_seniors'] = df_hh['household_id'].map(seniors_per_hh).fillna(0)
df_hh['has_seniors'] = df_hh['num_seniors'] > 0

print("="*80)
print("TOP 0.1% INCOME GROUP ANALYSIS")
print("="*80)
print()

# Overall top 0.1%
top_01 = df_hh[df_hh['is_top_01']]
print(f"Households in top 0.1%:")
print(f"  Sample count: {len(top_01):,}")
print(f"  Weighted count: {top_01['weight'].sum():,.0f}")
print(f"  Income threshold: ${top_01['household_net_income'].min():,.0f}")
print(f"  Average income: ${top_01['household_net_income'].mean():,.0f}")
print()

# Top 0.1% with seniors
top_01_with_seniors = top_01[top_01['has_seniors']]
print(f"Top 0.1% households WITH seniors (65+):")
print(f"  Sample count: {len(top_01_with_seniors):,}")
print(f"  Weighted count: {top_01_with_seniors['weight'].sum():,.0f}")
print(f"  Percentage of top 0.1%: {len(top_01_with_seniors) / len(top_01) * 100:.1f}%")
print(f"  Average # of seniors: {top_01_with_seniors['num_seniors'].mean():.1f}")
print()

# Top 0.1% receiving SS benefits
top_01_with_ss = top_01[top_01['ss_benefits'] > 0]
print(f"Top 0.1% households receiving Social Security:")
print(f"  Sample count: {len(top_01_with_ss):,}")
print(f"  Weighted count: {top_01_with_ss['weight'].sum():,.0f}")
print(f"  Percentage of top 0.1%: {len(top_01_with_ss) / len(top_01) * 100:.1f}%")
if len(top_01_with_ss) > 0:
    print(f"  Average SS benefit: ${top_01_with_ss['ss_benefits'].mean():,.0f}")
print()

# Top 0.1% with taxable SS benefits
top_01_with_taxable_ss = top_01[top_01['taxable_ss_benefits'] > 0]
print(f"Top 0.1% households with TAXABLE Social Security:")
print(f"  Sample count: {len(top_01_with_taxable_ss):,}")
print(f"  Weighted count: {top_01_with_taxable_ss['weight'].sum():,.0f}")
print(f"  Percentage of top 0.1%: {len(top_01_with_taxable_ss) / len(top_01) * 100:.1f}%")
if len(top_01_with_taxable_ss) > 0:
    print(f"  Average taxable SS: ${top_01_with_taxable_ss['taxable_ss_benefits'].mean():,.0f}")
print()

# Summary comparison
print("="*80)
print("SUMMARY")
print("="*80)
print(f"Top 0.1% households: {len(top_01):,}")
print(f"  - With seniors (65+): {len(top_01_with_seniors):,} ({len(top_01_with_seniors) / len(top_01) * 100:.1f}%)")
print(f"  - Receiving SS: {len(top_01_with_ss):,} ({len(top_01_with_ss) / len(top_01) * 100:.1f}%)")
print(f"  - With taxable SS: {len(top_01_with_taxable_ss):,} ({len(top_01_with_taxable_ss) / len(top_01) * 100:.1f}%)")
print()
print("✓ Analysis complete!")

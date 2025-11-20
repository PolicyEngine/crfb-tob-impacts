import sys
import os
repo_root = os.path.abspath('..')
src_path = os.path.join(repo_root, 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from policyengine_us import Microsimulation
from reforms import REFORMS
from tqdm import tqdm

print('='*80)
print('ALL REFORMS - HF TEST 2026 DATASET')
print('='*80)
print()

# Load baseline once
print('Loading baseline...')
baseline = Microsimulation(dataset='hf://policyengine/test/2026.h5')
baseline_tax = baseline.calculate('income_tax', period=2026, map_to='household')
print(f'✓ Baseline: ${baseline_tax.sum() / 1e9:.1f}B')
print()

results = []

for reform_id, reform_config in tqdm(REFORMS.items(), desc='Processing reforms'):
    reform_name = reform_config['name']
    reform_func = reform_config['func']

    print(f'\nProcessing {reform_id}: {reform_name[:50]}...')

    try:
        reform = reform_func()
        reform_sim = Microsimulation(dataset='hf://policyengine/test/2026.h5', reform=reform)
        reform_tax = reform_sim.calculate('income_tax', period=2026, map_to='household')

        impact = (reform_tax.sum() - baseline_tax.sum()) / 1e9

        results.append({
            'Reform ID': reform_id,
            'Reform Name': reform_name,
            'Revenue Impact ($B)': impact  # Keep full precision
        })

        print(f'  ✓ Impact: ${impact:.1f}B')

    except Exception as e:
        print(f'  ✗ Error: {e}')
        results.append({
            'Reform ID': reform_id,
            'Reform Name': reform_name,
            'Revenue Impact ($B)': 'ERROR'
        })

print()
print('='*80)
print('SUMMARY OF ALL REFORMS (2026)')
print('='*80)
print()

import pandas as pd
df = pd.DataFrame(results)
print(df.to_string(index=False))
print()

# Save to CSV
output_file = '../data/all_reforms_hf_test_2026.csv'
df.to_csv(output_file, index=False)
print(f'✓ Results saved to: {output_file}')
print()

print('='*80)
print('Dataset: hf://policyengine/test/2026.h5')
print('='*80)

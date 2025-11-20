import sys
import os
repo_root = os.path.abspath('..')
src_path = os.path.join(repo_root, 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from policyengine_us import Microsimulation
from reforms import REFORMS

print('Running Option 1 with hf://policyengine/test/2026.h5')
print('='*80)

baseline = Microsimulation(dataset='hf://policyengine/test/2026.h5')
option1_reform = REFORMS['option1']['func']()
reform = Microsimulation(dataset='hf://policyengine/test/2026.h5', reform=option1_reform)

print('Calculating for 2026...')
baseline_tax = baseline.calculate('income_tax', period=2026, map_to='household')
reform_tax = reform.calculate('income_tax', period=2026, map_to='household')

revenue_impact = (reform_tax.sum() - baseline_tax.sum()) / 1e9

print()
print('RESULTS')
print('='*80)
print(f'Baseline: ${baseline_tax.sum() / 1e9:.1f}B')
print(f'Reform:   ${reform_tax.sum() / 1e9:.1f}B')
print(f'Impact:   ${revenue_impact:.1f}B')
print()
print('Dataset: hf://policyengine/test/2026.h5')

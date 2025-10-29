"""
Calculate trust fund revenue from SS benefit taxation for Option 2.
"""
import sys
sys.path.insert(0, 'src')

from trust_fund_revenue import calculate_trust_fund_revenue
from reforms import get_option2_reform

# Calculate for 2026
revenue = calculate_trust_fund_revenue(
    reform=get_option2_reform(),
    year=2026
)

print(f"\n{'='*80}")
print(f"Trust Fund Revenue Calculation for Option 2 (2026)")
print(f"{'='*80}\n")
print(f"TOTAL trust fund revenue under Option 2 (85% taxation):")
print(f"  ${revenue / 1e9:.2f} billion")
print(f"  ${revenue / 1e6:.0f} million\n")
print(f"This represents the tax revenue flowing to Social Security trust funds")
print(f"from taxing 85% of all SS benefits under Option 2.\n")
print(f"Calculation method:")
print(f"  1. Run Option 2 simulation (85% taxation)")
print(f"  2. Create branch and neutralize tax_unit_taxable_social_security")
print(f"  3. Delete all calculated variables and recalculate income tax")
print(f"  4. Difference = trust fund revenue\n")

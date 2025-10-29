"""
Calculate trust fund revenue from SS benefit taxation for Option 2.
"""
import sys
sys.path.insert(0, 'src')

from trust_fund_revenue import calculate_trust_fund_revenue
from reforms import get_option2_reform

# Calculate for 2026
revenue_change = calculate_trust_fund_revenue(
    reform=get_option2_reform(),
    year=2026
)

print(f"\n{'='*80}")
print(f"Trust Fund Revenue Calculation for Option 2 (2026)")
print(f"{'='*80}\n")
print(f"Change in trust fund revenue from Option 2 vs baseline:")
print(f"  ${revenue_change / 1e9:.2f} billion")
print(f"  ${revenue_change / 1e6:.0f} million\n")
print(f"Note: This is the ADDITIONAL trust fund revenue from moving to")
print(f"      85% taxation (Option 2) compared to current law baseline.\n")

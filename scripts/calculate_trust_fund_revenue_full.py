"""
Calculate trust fund revenue from SS benefit taxation for Option 2.
Includes both static and conventional (with labor supply responses) calculations.
"""

import sys

sys.path.insert(0, "src")

from trust_fund_revenue import (
    calculate_trust_fund_revenue,
    calculate_trust_fund_revenue_conventional,
)
from reforms import get_option2_reform, tax_85_percent_ss
from policyengine_core.reforms import Reform

# CBO labor supply elasticities (simplified - no age multipliers)
CBO_LABOR_PARAMS = {
    # Income elasticity
    "gov.simulation.labor_supply_responses.elasticities.income": {
        "2024-01-01.2100-12-31": -0.05
    },
    # Substitution elasticities by decile for primary earners
    "gov.simulation.labor_supply_responses.elasticities.substitution.by_position_and_decile.primary.1": {
        "2024-01-01.2100-12-31": 0.31
    },
    "gov.simulation.labor_supply_responses.elasticities.substitution.by_position_and_decile.primary.2": {
        "2024-01-01.2100-12-31": 0.28
    },
    "gov.simulation.labor_supply_responses.elasticities.substitution.by_position_and_decile.primary.3": {
        "2024-01-01.2100-12-31": 0.27
    },
    "gov.simulation.labor_supply_responses.elasticities.substitution.by_position_and_decile.primary.4": {
        "2024-01-01.2100-12-31": 0.27
    },
    "gov.simulation.labor_supply_responses.elasticities.substitution.by_position_and_decile.primary.5": {
        "2024-01-01.2100-12-31": 0.25
    },
    "gov.simulation.labor_supply_responses.elasticities.substitution.by_position_and_decile.primary.6": {
        "2024-01-01.2100-12-31": 0.25
    },
    "gov.simulation.labor_supply_responses.elasticities.substitution.by_position_and_decile.primary.7": {
        "2024-01-01.2100-12-31": 0.22
    },
    "gov.simulation.labor_supply_responses.elasticities.substitution.by_position_and_decile.primary.8": {
        "2024-01-01.2100-12-31": 0.22
    },
    "gov.simulation.labor_supply_responses.elasticities.substitution.by_position_and_decile.primary.9": {
        "2024-01-01.2100-12-31": 0.22
    },
    "gov.simulation.labor_supply_responses.elasticities.substitution.by_position_and_decile.primary.10": {
        "2024-01-01.2100-12-31": 0.22
    },
    # Substitution elasticity for secondary earners
    "gov.simulation.labor_supply_responses.elasticities.substitution.by_position_and_decile.secondary": {
        "2024-01-01.2100-12-31": 0.27
    },
}

print("=" * 80)
print("Trust Fund Revenue Calculation for Option 2 (2026)")
print("=" * 80)

# Static calculation
print("\n1. STATIC CALCULATION (No behavioral responses)")
print("-" * 80)
revenue_static = calculate_trust_fund_revenue(reform=get_option2_reform(), year=2026)
print(f"Trust fund revenue (static): ${revenue_static / 1e9:.2f}B")

# Conventional calculation
print("\n2. CONVENTIONAL CALCULATION (With CBO labor supply elasticities)")
print("-" * 80)
option2_dict = tax_85_percent_ss()
option2_conventional_dict = {**option2_dict, **CBO_LABOR_PARAMS}
option2_conventional_reform = Reform.from_dict(option2_conventional_dict, country_id="us")

revenue_conventional = calculate_trust_fund_revenue_conventional(
    reform_with_labor_responses=option2_conventional_reform, year=2026
)
print(f"Trust fund revenue (conventional): ${revenue_conventional / 1e9:.2f}B")

# Comparison
print("\n" + "=" * 80)
print("COMPARISON")
print("=" * 80)
difference = revenue_conventional - revenue_static
pct_change = (difference / revenue_static) * 100

print(f"\nStatic:  ${revenue_static / 1e9:.2f}B")
print(f"Conventional: ${revenue_conventional / 1e9:.2f}B")
print(f"\nDifference: ${difference / 1e9:.2f}B ({pct_change:+.1f}%)")

if difference > 0:
    print(
        f"\nLabor supply responses INCREASE trust fund revenue by ${abs(difference) / 1e9:.2f}B"
    )
    print("This suggests that taxing SS benefits induces people to work more.")
else:
    print(
        f"\nLabor supply responses DECREASE trust fund revenue by ${abs(difference) / 1e9:.2f}B"
    )
    print("This suggests that taxing SS benefits induces people to work less.")

print()

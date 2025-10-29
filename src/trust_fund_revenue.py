"""
Calculate tax revenue flowing to Social Security trust funds from benefit taxation.

This module provides functions to calculate the portion of income tax revenue
that is attributable to taxation of Social Security benefits, which by law
flows to the Social Security trust funds.
"""
import numpy as np
from policyengine_us import Microsimulation
from typing import Optional


def calculate_trust_fund_revenue(
    reform,
    year: int,
    dataset: Optional[str] = None
) -> float:
    """
    Calculate TOTAL trust fund revenue from SS benefit taxation under a reform.

    Uses PolicyEngine's branching and neutralization to isolate the revenue component
    attributable to taxation of Social Security benefits by comparing:
    1. Income tax with the reform (including taxable SS benefits)
    2. Income tax with same conditions but tax_unit_taxable_social_security neutralized

    Args:
        reform: PolicyEngine Reform object
        year: Year to calculate for
        dataset: Optional dataset to use

    Returns:
        Trust fund revenue in dollars (positive = revenue to trust funds)
        This is the TOTAL revenue, not the change from baseline.
    """
    # Create simulation with the reform
    if dataset:
        sim = Microsimulation(reform=reform, dataset=dataset)
    else:
        sim = Microsimulation(reform=reform)

    # Calculate income tax WITH SS taxation
    income_tax_with_ss = sim.calculate("income_tax", map_to="household", period=year)

    # Verify we have taxable SS
    taxable_ss_unit = sim.calculate("tax_unit_taxable_social_security", period=year)
    if taxable_ss_unit.sum() == 0:
        return 0.0  # No taxable SS means no trust fund revenue

    # Create branch and neutralize tax_unit_taxable_social_security
    branch = sim.get_branch("trust_fund_calc", clone_system=True)
    branch.tax_benefit_system.neutralize_variable("tax_unit_taxable_social_security")

    # Delete ALL calculated variables to force complete recalculation
    # (keeping only input variables)
    for var_name in list(branch.tax_benefit_system.variables.keys()):
        if var_name not in branch.input_variables:
            try:
                branch.delete_arrays(var_name)
            except:
                pass

    # Calculate income tax WITHOUT taxable SS
    income_tax_without_ss = branch.calculate("income_tax", map_to="household", period=year)

    # Clean up branch
    del sim.branches["trust_fund_calc"]

    # Trust fund revenue = difference (TOTAL revenue, not change from baseline)
    trust_fund_revenue = income_tax_with_ss.sum() - income_tax_without_ss.sum()

    return float(trust_fund_revenue)


def calculate_trust_fund_revenue_dynamic(
    reform_with_labor_responses,
    year: int,
    dataset: Optional[str] = None
) -> float:
    """
    Calculate trust fund revenue with labor supply responses.

    This uses the correct methodology for dynamic models:
    1. Run simulation with reform + labor supply elasticities
    2. Extract behaviorally-adjusted employment income
    3. Create branch, neutralize taxable_social_security, override incomes
    4. Recalculate income tax with fixed incomes
    5. Difference = trust fund revenue accounting for behavioral responses

    Args:
        reform_with_labor_responses: Reform object with labor elasticities included
        year: Year to calculate for
        dataset: Optional dataset to use

    Returns:
        Trust fund revenue in dollars (positive = revenue to trust funds)
    """
    # Create simulation with reform + labor responses
    if dataset:
        sim = Microsimulation(reform=reform_with_labor_responses, dataset=dataset)
    else:
        sim = Microsimulation(reform=reform_with_labor_responses)

    # Calculate income tax WITH SS taxation and behavioral responses
    income_tax_with_ss = sim.calculate("income_tax", map_to="household", period=year)

    # Verify we have taxable SS
    taxable_ss_unit = sim.calculate("tax_unit_taxable_social_security", period=year)
    if taxable_ss_unit.sum() == 0:
        return 0.0  # No taxable SS means no trust fund revenue

    # Extract behaviorally-adjusted employment income (already includes LSR)
    employment_income = sim.calculate("employment_income", map_to="person", period=year)
    self_employment_income = sim.calculate("self_employment_income", map_to="person", period=year)

    # Create branch and neutralize BOTH tax_unit_taxable_social_security AND LSR variables
    branch = sim.get_branch("trust_fund_calc", clone_system=True)
    branch.tax_benefit_system.neutralize_variable("tax_unit_taxable_social_security")

    # Neutralize all LSR variables so they return 0 (disables behavioral responses in branch)
    branch.tax_benefit_system.neutralize_variable("labor_supply_behavioral_response")
    branch.tax_benefit_system.neutralize_variable("employment_income_behavioral_response")
    branch.tax_benefit_system.neutralize_variable("self_employment_income_behavioral_response")
    branch.tax_benefit_system.neutralize_variable("income_elasticity_lsr")
    branch.tax_benefit_system.neutralize_variable("substitution_elasticity_lsr")

    # Set the total employment income (with behavioral adjustments) as the base input
    # Since LSR is neutralized, employment_income will just use employment_income_before_lsr
    branch.set_input("employment_income_before_lsr", year, employment_income)
    branch.set_input("self_employment_income_before_lsr", year, self_employment_income)

    # Delete ALL calculated variables to force complete recalculation
    for var_name in list(branch.tax_benefit_system.variables.keys()):
        if var_name not in branch.input_variables:
            try:
                branch.delete_arrays(var_name)
            except:
                pass

    # Calculate income tax with fixed incomes but no taxable SS
    income_tax_without_ss = branch.calculate("income_tax", map_to="household", period=year)

    # Clean up
    del sim.branches["trust_fund_calc"]

    # Trust fund revenue = difference (TOTAL revenue, not change from baseline)
    trust_fund_revenue = income_tax_with_ss.sum() - income_tax_without_ss.sum()

    return float(trust_fund_revenue)

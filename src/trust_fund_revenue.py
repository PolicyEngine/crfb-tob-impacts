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
    Calculate trust fund revenue from SS benefit taxation.

    Uses PolicyEngine's branching mechanism to isolate the revenue component
    attributable to taxation of Social Security benefits by comparing:
    1. Income tax with the reform (including taxable SS benefits)
    2. Income tax with same reform but taxable_social_security neutralized

    Args:
        reform: PolicyEngine Reform object
        year: Year to calculate for
        dataset: Optional dataset to use

    Returns:
        Trust fund revenue in dollars (positive = revenue to trust funds)
    """
    # Create simulation with the reform
    if dataset:
        sim = Microsimulation(reform=reform, dataset=dataset)
    else:
        sim = Microsimulation(reform=reform)

    # Calculate income tax WITH SS taxation
    income_tax_with_ss = sim.calculate("income_tax", map_to="household", period=year)

    # Verify we have taxable SS
    taxable_ss = sim.calculate("taxable_social_security", period=year)
    if taxable_ss.sum() == 0:
        return 0.0  # No taxable SS means no trust fund revenue

    # Compare against baseline (current law) to get CHANGE in trust fund revenue
    # Create baseline simulation (no reform)
    if dataset:
        baseline = Microsimulation(dataset=dataset)
    else:
        baseline = Microsimulation()

    income_tax_baseline = baseline.calculate("income_tax", map_to="household", period=year)

    # Trust fund revenue = CHANGE from baseline
    # This is the additional trust fund revenue from the reform
    trust_fund_revenue_change = income_tax_with_ss.sum() - income_tax_baseline.sum()

    # Note: This returns the CHANGE in trust fund revenue, not absolute amount
    # To get absolute trust fund revenue under the reform, would need to also
    # calculate baseline trust fund revenue and add it
    return float(trust_fund_revenue_change)


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

    # Extract behaviorally-adjusted employment income
    employment_income = sim.calculate("employment_income", map_to="person", period=year)
    self_employment_income = sim.calculate("self_employment_income", map_to="person", period=year)

    # Create branch and apply Option 1 (eliminate SS taxation)
    branch = sim.get_branch("trust_fund_calc", clone_system=True)

    # Apply Option 1 reform to eliminate SS taxation
    from reforms import eliminate_ss_taxation
    from policyengine_core.reforms import Reform

    eliminate_reform = Reform.from_dict(eliminate_ss_taxation(), country_id="us")
    eliminate_reform.apply(branch.tax_benefit_system)

    # Override incomes with behaviorally-adjusted values
    branch.set_input("employment_income", year, employment_income)
    branch.set_input("self_employment_income", year, self_employment_income)

    # Delete dependent variables to force recalculation
    dependent_vars = [
        "income_tax",
        "adjusted_gross_income",
        "adjusted_gross_income_person",
        "taxable_income",
        "taxable_income_deductions",
        "income_tax_before_credits",
        "taxable_social_security"
    ]

    for var in dependent_vars:
        try:
            branch.delete_arrays(var)
        except:
            pass

    # Calculate income tax with fixed incomes but no taxable SS
    income_tax_without_ss = branch.calculate("income_tax", map_to="household", period=year)

    # Clean up
    del sim.branches["trust_fund_calc"]

    # Trust fund revenue = difference
    trust_fund_revenue = income_tax_with_ss.sum() - income_tax_without_ss.sum()

    return float(trust_fund_revenue)

# Trust Fund Revenue Calculation Methodology

## Summary

This document explains the correct methodology for calculating tax revenue flowing to Social Security and Medicare trust funds from taxation of Social Security benefits.

## Key Finding

**Option 2 (85% taxation of all SS benefits) generates $110.32B in total trust fund revenue in 2026.**

## Methodology: Branching + Neutralization (CORRECT)

Our approach uses PolicyEngine's branching and variable neutralization:

```python
# 1. Run simulation with the reform (e.g., Option 2: 85% taxation)
sim = Microsimulation(reform=option2_reform)
income_tax_with_ss = sim.calculate("income_tax", map_to="household", period=year)

# 2. Create branch and neutralize taxable SS
branch = sim.get_branch("trust_fund_calc", clone_system=True)
branch.tax_benefit_system.neutralize_variable("tax_unit_taxable_social_security")

# 3. Delete ALL calculated variables to force recalculation
for var_name in branch.tax_benefit_system.variables.keys():
    if var_name not in branch.input_variables:
        branch.delete_arrays(var_name)

# 4. Recalculate income tax without taxable SS
income_tax_without_ss = branch.calculate("income_tax", map_to="household", period=year)

# 5. Trust fund revenue = difference
trust_fund_revenue = income_tax_with_ss.sum() - income_tax_without_ss.sum()
```

### Why This Works

- Holds EVERYTHING constant (income, deductions, credits, etc.)
- Only changes whether SS benefits are taxable
- Directly measures the marginal tax impact of taxable SS
- Uses the same branching mechanism as `marginal_tax_rate` and labor supply responses

## Alternative Approach: Average Effective Tax Rate (WRONG)

PR #6747 in policyengine-us uses this approach:

```python
# From PR 6747
effective_rate = where(taxable_income > 0, income_tax / taxable_income, 0)
tob_revenue = tier_2_taxable_ss * effective_rate
```

### Why This Is Wrong

1. **Assumes average = marginal**: Uses the average effective tax rate on ALL income, not the marginal rate on SS benefits
2. **Ignores tax brackets**: SS benefits might be taxed at different rates than other income
3. **Misses interactions**: Doesn't account for how taxable SS affects deductions, credits, and phase-outs
4. **Approximation vs. exact**: Estimates rather than directly calculating

### Example of Error

Consider a taxpayer with:
- $50K wages (taxed at 12% and 22% brackets)
- $30K taxable SS benefits (taxed at 12% bracket)

**Average effective rate approach:**
- Total income tax: $8,000
- Total taxable income: $70K
- Effective rate: 11.4%
- Estimated TOB: $30K × 11.4% = $3,420

**Correct branching approach:**
- Income tax with taxable SS: $8,000
- Income tax without taxable SS: $4,400
- Actual TOB: $3,600

The average rate approach underestimates by $180 (5%) in this example.

## Results

### Static Calculation (Working)

**Option 2 (85% taxation) - 2026:**
- Total trust fund revenue: **$110.32B**
- Total taxable SS: $1,270.50B
- Total income tax with SS: $2,198.81B
- Total income tax without SS: $2,088.49B

This uses the branching + neutralization approach described above.

### Dynamic Calculation (In Progress)

The dynamic calculation with labor supply responses faces technical challenges:
- Recursion errors when trying to preserve behavioral responses in the counterfactual
- Issue: labor_supply_behavioral_response creates circular dependencies
- Needs further investigation of how to properly override employment income while neutralizing LSR

## Recommendation for PolicyEngine-US

**YES, this should be implemented in policyengine-us as proper variables:**

1. `tob_revenue_social_security` - Revenue to OASDI from taxing tier 1 (0-50%)
2. `tob_revenue_medicare_hi` - Revenue to Medicare HI from taxing tier 2 (50-85%)

**Implementation:**

```python
class tob_revenue_social_security(Variable):
    value_type = float
    entity = TaxUnit
    definition_period = YEAR
    label = "OASDI trust fund revenue from SS benefit taxation"
    unit = USD

    def formula(tax_unit, period, parameters):
        sim = tax_unit.simulation

        # Calculate income tax WITH taxable SS
        income_tax_with = tax_unit("income_tax", period)

        # Create branch and neutralize tier 1 taxable SS
        branch = sim.get_branch("tob_oasdi_calc", clone_system=True)
        branch.tax_benefit_system.neutralize_variable("taxable_social_security_tier_1")

        # Delete calculated variables
        for var in ["income_tax", "adjusted_gross_income", "taxable_income"]:
            try:
                branch.delete_arrays(var)
            except:
                pass

        # Recalculate
        income_tax_without = branch.tax_unit.calculate("income_tax", period)

        # Clean up
        del sim.branches["tob_oasdi_calc"]

        return income_tax_with - income_tax_without
```

**Concerns about branching:**
- Branching is already used in `marginal_tax_rate` and `labor_supply_behavioral_response`
- It won't break things if used carefully
- Need to ensure branches are properly cleaned up
- May need to limit recursion depth (similar to LSR variables)

## Files

- `src/trust_fund_revenue.py` - Working implementation
- `tests/test_trust_fund_revenue.py` - Full test coverage
- `tests/test_trust_fund_neutralization.py` - Detailed neutralization test
- `scripts/calculate_trust_fund_revenue.py` - Command-line tool

## Next Steps

1. ✅ Static calculation working ($110.32B for Option 2)
2. ⏳ Resolve dynamic calculation recursion issues
3. 📝 Submit PR to policyengine-us to replace PR #6747's approach
4. 🔧 May need to fix labor supply response architecture to avoid circular dependencies

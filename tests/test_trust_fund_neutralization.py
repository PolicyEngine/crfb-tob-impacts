"""
Test that neutralizing tax_unit_taxable_social_security works correctly.
"""
from policyengine_us import Microsimulation
from src.reforms import get_option2_reform


def test_neutralize_tax_unit_taxable_ss():
    """Test that neutralizing tax_unit_taxable_social_security reduces income tax."""
    reform = get_option2_reform()
    sim = Microsimulation(reform=reform)
    year = 2026

    # Calculate income tax WITH taxable SS
    income_tax_with = sim.calculate("income_tax", map_to="household", period=year)
    taxable_ss_with = sim.calculate("tax_unit_taxable_social_security", period=year)

    print(f"With SS taxation:")
    print(f"  Taxable SS: ${taxable_ss_with.sum() / 1e9:.2f}B")
    print(f"  Income tax: ${income_tax_with.sum() / 1e9:.2f}B")

    assert taxable_ss_with.sum() > 0, "Should have taxable SS under Option 2"

    # Create branch and neutralize TAX_UNIT variable (not person-level)
    branch = sim.get_branch("test", clone_system=True)
    branch.tax_benefit_system.neutralize_variable("tax_unit_taxable_social_security")

    # Delete ALL variables to force complete recalculation
    # Get all calculated variables (anything that's not an input)
    print("\nDeleting all calculated variables to force recalculation...")
    for var_name in list(branch.tax_benefit_system.variables.keys()):
        if var_name not in branch.input_variables:
            try:
                branch.delete_arrays(var_name)
            except:
                pass

    income_tax_without = branch.calculate("income_tax", map_to="household", period=year)
    taxable_ss_without = branch.calculate("tax_unit_taxable_social_security", period=year)

    print(f"\nWithout SS taxation (neutralized):")
    print(f"  Taxable SS: ${taxable_ss_without.sum() / 1e9:.2f}B")
    print(f"  Income tax: ${income_tax_without.sum() / 1e9:.2f}B")

    print(f"\nDifference:")
    print(f"  Trust fund revenue: ${(income_tax_with.sum() - income_tax_without.sum()) / 1e9:.2f}B")

    assert taxable_ss_without.sum() == 0, "Neutralized taxable SS should be 0"
    assert income_tax_with.sum() > income_tax_without.sum(), \
        "Income tax with SS taxation should be higher"
    assert (income_tax_with.sum() - income_tax_without.sum()) > 10e9, \
        "Trust fund revenue should be substantial (>$10B)"


if __name__ == "__main__":
    test_neutralize_tax_unit_taxable_ss()

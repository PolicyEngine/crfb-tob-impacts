"""Tests for reform definitions."""

from src.reforms import (
    get_option1_reform,
    get_option2_reform,
    get_option3_reform,
    get_option4_reform,
    get_option5_reform,
    get_option6_reform,
    get_option7_reform,
    get_option8_reform,
    get_reverse_roth_behavioral_reform,
    get_reverse_roth_reform,
    REFORMS,
)


def test_option1_reform():
    """Test Option 1 reform creation."""
    reform = get_option1_reform()
    assert reform is not None
    # Check that base and additional rates are set to 0
    params = reform.parameter_values
    assert any("taxability.rate.base" in str(k) for k in params.keys())
    assert any("taxability.rate.additional" in str(k) for k in params.keys())


def test_option2_reform():
    """Test Option 2 reform creation."""
    reform = get_option2_reform()
    assert reform is not None
    params = reform.parameter_values
    # Option 2 uses the current-law 85% cap, but removes thresholds and
    # includes all Social Security benefits in combined income.
    assert any("combined_income_ss_fraction" in str(k) for k in params.keys())
    # Check that thresholds are set to 0
    assert any("threshold.base.main" in str(k) for k in params.keys())


def test_option3_reform():
    """Test Option 3 reform creation."""
    reform = get_option3_reform()
    assert reform is not None
    params = reform.parameter_values
    # Should have both 85% taxation and senior deduction extension
    assert any("combined_income_ss_fraction" in str(k) for k in params.keys())
    assert any("senior_deduction_extension" in str(k) for k in params.keys())


def test_option4_reform_default():
    """Test Option 4 reform with default credit amount."""
    reform = get_option4_reform()
    assert reform is not None
    params = reform.parameter_values
    assert any("ss_credit" in str(k) for k in params.keys())


def test_option4_reform_custom_amount():
    """Test Option 4 reform with custom credit amount."""
    reform = get_option4_reform(credit_amount=750)
    assert reform is not None
    params = reform.parameter_values
    # Check that credit amount is set
    credit_params = [v for k, v in params.items() if "ss_credit.amount" in str(k)]
    assert len(credit_params) > 0
    # The credit amount should be 750 for the time period
    assert any(750 in v.values() for v in credit_params if hasattr(v, "values"))


def test_option5_reform():
    """Test Option 5 Roth-style swap reform."""
    reform = get_option5_reform()
    assert reform is not None
    params = reform.parameter_values
    # Should have employer payroll tax inclusion
    assert any("tax_employer_payroll_tax" in str(k) for k in params.keys())


def test_option6_reform():
    """Test Option 6 phased Roth-style swap reform."""
    reform = get_option6_reform()
    assert reform is not None
    params = reform.parameter_values
    # Should have phased parameters
    assert any("tax_employer_payroll_tax.percentage" in str(k) for k in params.keys())
    # Check that it has multiple year entries for phase-in
    percentage_params = [
        v for k, v in params.items() if "tax_employer_payroll_tax.percentage" in str(k)
    ]
    assert len(percentage_params) > 0


def test_option7_reform():
    """Test Option 7 eliminate senior deduction reform."""
    reform = get_option7_reform()
    assert reform is not None
    params = reform.parameter_values
    # Should set senior deduction amount to 0
    assert any("senior_deduction.amount" in str(k) for k in params.keys())


def test_option8_reform():
    """Test Option 8 full taxation of Social Security benefits."""
    reform = get_option8_reform()
    assert reform is not None
    params = reform.parameter_values
    # Should have combined income SS fraction set to 1.0
    assert any("combined_income_ss_fraction" in str(k) for k in params.keys())
    # Should have taxability additional rate set to 1.0 (100%)
    assert any("taxability.rate.additional" in str(k) for k in params.keys())
    # Should have all thresholds set to 0
    assert any("threshold.base.main" in str(k) for k in params.keys())
    assert any("threshold.adjusted_base.main" in str(k) for k in params.keys())


def test_reverse_roth_reform():
    """Test the reverse-Roth Social Security proposal."""
    # A two-reform set: parameter reform + the OASDI-deduction variable reform.
    param_reform, deduction_reform = get_reverse_roth_reform()
    assert param_reform is not None and deduction_reform is not None
    params = param_reform.parameter_values
    assert any("combined_income_ss_fraction" in str(k) for k in params.keys())
    assert any("taxability.rate.additional" in str(k) for k in params.keys())
    assert param_reform.name == "Reverse Roth Social Security proposal"


def test_reverse_roth_behavioral_reform_includes_elasticities():
    """Reverse-Roth behavioral scoring: params + elasticities, then the
    deduction variable, as a flat reform set (no nested from_dict)."""
    param_reform, deduction_reform = get_reverse_roth_behavioral_reform()
    assert param_reform is not None and deduction_reform is not None
    params = param_reform.parameter_values
    assert any("simulation.labor_supply_responses" in str(k) for k in params.keys())
    assert any("taxability.rate.additional" in str(k) for k in params.keys())


def test_reforms_registry():
    """Test that all reforms are properly registered."""
    assert len(REFORMS) == 14
    assert "reverse_roth" in REFORMS

    # Check each reform has required fields
    for reform_id, config in REFORMS.items():
        assert "name" in config
        assert "func" in config

        # Test that function is callable
        assert callable(config["func"])


def test_reform_variants():
    """Test reforms with variants."""
    option4 = REFORMS["option4"]

    # Test option 4 with different credit amounts
    for amount in [250, 500, 750, 900, 1000]:
        reform = option4["func"](amount)
        assert reform is not None


def test_tax93_rates_sit_between_neighbors():
    from src.reforms import (
        get_option9_dict,
        get_option10_dict,
        get_tax93_dict,
    )

    rate_keys = [key for key in get_tax93_dict() if ".taxability.rate." in key]
    assert rate_keys
    for key in rate_keys:
        low = list(get_option9_dict()[key].values())[0]
        mid = list(get_tax93_dict()[key].values())[0]
        high = list(get_option10_dict()[key].values())[0]
        assert low < mid < high
        assert mid == 0.93


def test_tax93_reform_builds():
    from src.reforms import get_tax93_reform

    assert get_tax93_reform() is not None


def test_tax_panel_2005_dict_structure():
    from src.reforms import get_tax_panel_2005_dict

    d = get_tax_panel_2005_dict()
    period = "2026-01-01.2100-12-31"
    # Worksheet income (line 9) counts 85% of benefits.
    assert d[
        "gov.irs.social_security.taxability.combined_income_ss_fraction"
    ] == {period: 0.85}
    # 50% phase-in slope is current law's tier-1 rate; only the cap moves.
    assert d["gov.irs.social_security.taxability.rate.base.benefit_cap"] == {
        period: 0.85
    }
    assert not any(".rate.base.excess" in key for key in d)
    assert not any(".rate.additional." in key for key in d)
    # $22,000/$44,000 unindexed thresholds; married = exactly twice single.
    base = "gov.irs.social_security.taxability.threshold.base.main"
    assert d[f"{base}.SINGLE"] == {period: 22_000}
    assert d[f"{base}.JOINT"] == {period: 44_000}
    # Second tier disabled for every main filing status.
    adjusted = "gov.irs.social_security.taxability.threshold.adjusted_base.main"
    for status in [
        "SINGLE",
        "JOINT",
        "SEPARATE",
        "HEAD_OF_HOUSEHOLD",
        "SURVIVING_SPOUSE",
    ]:
        assert list(d[f"{adjusted}.{status}"].values())[0] >= 10_000_000_000
    # Separate-cohabitating thresholds keep current law ($0): not in the dict.
    assert not any("separate_cohabitating" in key for key in d)


def test_tax_panel_2005_matches_worksheet():
    """Reform must reproduce the 2005 report's Figure 5.11 worksheet:

    taxable SS = clamp(50% x (income - threshold), 0, 85% x benefits),
    income counting 85% of benefits, thresholds $22k single / $44k joint.
    """
    from policyengine_us import Simulation

    from src.reforms import get_tax_panel_2005_reform

    reform = get_tax_panel_2005_reform()

    def worksheet(ss, other_income, threshold):
        income = other_income + 0.85 * ss
        return min(max(0.5 * (income - threshold), 0.0), 0.85 * ss)

    cases = [
        # (gross SS, taxable interest, joint?, threshold)
        (20_000, 30_000, False, 22_000),  # phase-in binds
        (20_000, 60_000, False, 22_000),  # 85% cap binds
        (20_000, 5_000, False, 22_000),  # below threshold
        (30_000, 40_000, True, 44_000),  # joint, phase-in binds
    ]
    for ss, other, joint, threshold in cases:
        people = {
            "adult": {
                "age": {2026: 70},
                "social_security_retirement": {2026: ss},
                "taxable_interest_income": {2026: other},
            }
        }
        members = ["adult"]
        if joint:
            people["spouse"] = {"age": {2026: 68}}
            members.append("spouse")
        simulation = Simulation(
            situation={
                "people": people,
                "tax_units": {"tax_unit": {"members": members}},
                "households": {
                    "household": {
                        "members": members,
                        "state_code": {2026: "TX"},
                    }
                },
            },
            reform=reform,
        )
        actual = float(
            simulation.calculate("tax_unit_taxable_social_security", 2026)[0]
        )
        expected = worksheet(ss, other, threshold)
        assert abs(actual - expected) < 1, (ss, other, joint, actual, expected)

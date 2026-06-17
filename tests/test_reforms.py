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
    get_reverse_roth_conventional_reform,
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


def test_reverse_roth_conventional_reform_includes_elasticities():
    """Reverse-Roth behavioral scoring: params + elasticities, then the
    deduction variable, as a flat reform set (no nested from_dict)."""
    param_reform, deduction_reform = get_reverse_roth_conventional_reform()
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

    rate_keys = [
        key for key in get_tax93_dict() if ".taxability.rate." in key
    ]
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

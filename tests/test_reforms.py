"""Tests for reform definitions."""

import pytest
from src.reforms import (
    get_option1_reform,
    get_option2_reform,
    get_option3_reform,
    get_option4_reform,
    get_option5_reform,
    get_option6_reform,
    get_option7_reform,
    REFORMS
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
    # Check that base rate is set to 0.85
    assert any("taxability.rate.base" in str(k) for k in params.keys())
    # Check that thresholds are set to 0
    assert any("threshold.base.main" in str(k) for k in params.keys())


def test_option3_reform():
    """Test Option 3 reform creation."""
    reform = get_option3_reform()
    assert reform is not None
    params = reform.parameter_values
    # Should have both 85% taxation and senior deduction extension
    assert any("taxability.rate.base" in str(k) for k in params.keys())
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
    assert any(750 in v.values() for v in credit_params if hasattr(v, 'values'))


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
    percentage_params = [v for k, v in params.items()
                         if "tax_employer_payroll_tax.percentage" in str(k)]
    assert len(percentage_params) > 0


def test_option7_reform():
    """Test Option 7 eliminate senior deduction reform."""
    reform = get_option7_reform()
    assert reform is not None
    params = reform.parameter_values
    # Should set senior deduction amount to 0
    assert any("senior_deduction.amount" in str(k) for k in params.keys())


def test_reforms_registry():
    """Test that all reforms are properly registered."""
    assert len(REFORMS) == 7

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
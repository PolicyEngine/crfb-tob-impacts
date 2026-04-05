"""Tests for reform definitions."""

import pytest
from src.reforms import (
    get_option10_reform,
    get_option11_reform,
    get_option12_reform,
    get_option1_reform,
    get_option2_reform,
    get_option3_reform,
    get_option4_reform,
    get_option5_reform,
    get_option6_reform,
    get_option7_reform,
    get_option8_reform,
    get_option9_reform,
    REFORMS,
)


def test_option1_reform_zeroes_all_ss_taxability_rates():
    """Option 1 should zero all current-law Social Security taxability rates."""
    params = get_option1_reform().parameter_values

    expected = {
        "gov.irs.social_security.taxability.rate.base.benefit_cap",
        "gov.irs.social_security.taxability.rate.base.excess",
        "gov.irs.social_security.taxability.rate.additional.benefit_cap",
        "gov.irs.social_security.taxability.rate.additional.bracket",
        "gov.irs.social_security.taxability.rate.additional.excess",
    }
    assert set(params) == expected
    for key in expected:
        assert params[key] == {"2026-01-01.2100-12-31": 0}


def test_option2_reform():
    """Option 2 should set full combined-income inclusion and zero thresholds."""
    params = get_option2_reform().parameter_values

    assert params["gov.irs.social_security.taxability.combined_income_ss_fraction"] == {
        "2026-01-01.2100-12-31": 1.0
    }
    threshold_keys = [
        key
        for key in params
        if ".threshold.base.main." in key or ".threshold.adjusted_base.main." in key
    ]
    assert len(threshold_keys) == 10
    for key in threshold_keys:
        assert params[key] == {"2026-01-01.2100-12-31": 0}
    assert not any(
        key.startswith("gov.irs.social_security.taxability.rate.") for key in params
    )


def test_option3_reform():
    """Option 3 should add the senior-deduction extension on top of option 2."""
    params = get_option3_reform().parameter_values

    assert params["gov.irs.social_security.taxability.combined_income_ss_fraction"] == {
        "2026-01-01.2100-12-31": 1.0
    }
    assert params["gov.contrib.crfb.senior_deduction_extension.applies"] == {
        "2026-01-01.2100-12-31": True
    }
    assert not any(
        key.startswith("gov.irs.social_security.taxability.rate.") for key in params
    )


def test_option4_reform_default():
    """Option 4 should enable the SS credit with the default $500 amount."""
    params = get_option4_reform().parameter_values

    assert params["gov.contrib.crfb.ss_credit.in_effect"] == {
        "2026-01-01.2100-12-31": True
    }
    assert params["gov.contrib.crfb.ss_credit.amount.JOINT"] == {
        "2026-01-01.2100-12-31": 500
    }


def test_option4_reform_custom_amount():
    """Option 4 should apply a caller-provided credit amount to all filing types."""
    params = get_option4_reform(credit_amount=750).parameter_values

    for filing_status in [
        "JOINT",
        "SINGLE",
        "SEPARATE",
        "SURVIVING_SPOUSE",
        "HEAD_OF_HOUSEHOLD",
    ]:
        assert params[f"gov.contrib.crfb.ss_credit.amount.{filing_status}"] == {
            "2026-01-01.2100-12-31": 750
        }


def test_option5_reform():
    """Option 5 should fully tax employer payroll contributions immediately."""
    params = get_option5_reform().parameter_values

    assert params["gov.contrib.crfb.tax_employer_payroll_tax.in_effect"] == {
        "2026-01-01.2100-12-31": True
    }
    assert params["gov.contrib.crfb.tax_employer_payroll_tax.percentage"] == {
        "2026-01-01.2100-12-31": 1.0
    }


def test_option6_reform():
    """Option 6 should phase in employer-tax inclusion and phase out benefit taxation."""
    params = get_option6_reform().parameter_values
    phase_in = params["gov.contrib.crfb.tax_employer_payroll_tax.percentage"]

    assert phase_in["2026"] == pytest.approx(0.1307)
    assert phase_in["2033-01-01.2100-12-31"] == 1.0
    assert params["gov.irs.social_security.taxability.rate.additional.bracket"][
        "2045-01-01.2100-12-31"
    ] == 0


def test_option7_reform():
    """Option 7 should eliminate the bonus senior deduction."""
    params = get_option7_reform().parameter_values

    assert params["gov.irs.deductions.senior_deduction.amount"] == {
        "2026-01-01.2100-12-31": 0
    }


@pytest.mark.parametrize(
    ("factory", "expected_rate"),
    [
        (get_option8_reform, 1.0),
        (get_option9_reform, 0.9),
        (get_option10_reform, 0.95),
    ],
)
def test_high_taxability_reforms_set_expected_rates(factory, expected_rate):
    """Options 8-10 should differ only by their taxability-rate target."""
    params = factory().parameter_values

    assert params["gov.irs.social_security.taxability.combined_income_ss_fraction"] == {
        "2026-01-01.2100-12-31": 1.0
    }
    assert params["gov.irs.social_security.taxability.rate.base.benefit_cap"] == {
        "2026-01-01.2100-12-31": expected_rate
    }
    assert params["gov.irs.social_security.taxability.rate.additional.benefit_cap"] == {
        "2026-01-01.2100-12-31": expected_rate
    }
    assert params["gov.irs.social_security.taxability.rate.additional.bracket"] == {
        "2026-01-01.2100-12-31": expected_rate
    }


def test_reforms_registry():
    """Test that all reforms are properly registered."""
    assert list(REFORMS) == [f"option{i}" for i in range(1, 13)]

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
        assert reform.parameter_values["gov.contrib.crfb.ss_credit.amount.JOINT"] == {
            "2026-01-01.2100-12-31": amount
        }


def test_option11_reform_enables_phase_out_credit():
    """Option 11 should use a $700 credit with the phase-out enabled."""
    params = get_option11_reform().parameter_values

    assert params["gov.contrib.crfb.ss_credit.amount.JOINT"] == {
        "2026-01-01.2100-12-31": 700
    }
    assert params["gov.contrib.crfb.ss_credit.phase_out.applies"] == {
        "2026-01-01.2100-12-31": True
    }


def test_option12_reform_uses_extended_phase_out_schedule():
    """Option 12 should fully tax employer payroll and phase out benefit taxation."""
    params = get_option12_reform().parameter_values

    assert params["gov.contrib.crfb.tax_employer_payroll_tax.percentage"] == {
        "2026-01-01.2100-12-31": 1.0
    }
    assert params["gov.ssa.revenue.oasdi_share_of_gross_ss"]["2029"] == pytest.approx(
        0.475
    )
    assert params["gov.ssa.revenue.oasdi_share_of_gross_ss"]["2048"] == 0.0
    assert params["gov.ssa.revenue.oasdi_share_of_gross_ss"][
        "2049-01-01.2100-12-31"
    ] == 0
    assert params["gov.irs.social_security.taxability.rate.additional.benefit_cap"][
        "2063-01-01.2100-12-31"
    ] == 0

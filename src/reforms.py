"""
Policy reform definitions for Social Security taxation analysis.

This module contains functions that return Reform objects for different
Social Security taxation policy options.
"""

from policyengine_core.reforms import Reform
from policyengine_us.model_api import *


# Common reform components as modular functions

def zero_ss_tax_thresholds():
    """Set all Social Security taxation thresholds to zero."""
    return {
        "gov.irs.social_security.taxability.threshold.base.main.JOINT": {
            "2026-01-01.2100-12-31": 0
        },
        "gov.irs.social_security.taxability.threshold.base.main.SINGLE": {
            "2026-01-01.2100-12-31": 0
        },
        "gov.irs.social_security.taxability.threshold.base.main.SEPARATE": {
            "2026-01-01.2100-12-31": 0
        },
        "gov.irs.social_security.taxability.threshold.base.main.SURVIVING_SPOUSE": {
            "2026-01-01.2100-12-31": 0
        },
        "gov.irs.social_security.taxability.threshold.base.main.HEAD_OF_HOUSEHOLD": {
            "2026-01-01.2100-12-31": 0
        }
    }


def eliminate_ss_taxation():
    """Eliminate Social Security benefit taxation."""
    return {
        "gov.irs.social_security.taxability.rate.base": {
            "2026-01-01.2100-12-31": 0
        },
        "gov.irs.social_security.taxability.rate.additional": {
            "2026-01-01.2100-12-31": 0
        }
    }


def tax_85_percent_ss():
    """Tax 85% of Social Security benefits for all recipients.

    This reform makes 85% of Social Security benefits taxable regardless
    of income level. Uses the PR #6562 parametric approach by setting
    combined_income_ss_fraction to 1.0 and all thresholds to 0.
    """
    return {
        # Set combined income fraction to 1.0 (instead of 0.5)
        # This ensures combined income includes full SS amount
        "gov.irs.social_security.taxability.combined_income_ss_fraction": {
            "2026-01-01.2100-12-31": 1.0
        },
        # Set all base thresholds to 0
        "gov.irs.social_security.taxability.threshold.base.main.JOINT": {
            "2026-01-01.2100-12-31": 0
        },
        "gov.irs.social_security.taxability.threshold.base.main.SINGLE": {
            "2026-01-01.2100-12-31": 0
        },
        "gov.irs.social_security.taxability.threshold.base.main.SEPARATE": {
            "2026-01-01.2100-12-31": 0
        },
        "gov.irs.social_security.taxability.threshold.base.main.SURVIVING_SPOUSE": {
            "2026-01-01.2100-12-31": 0
        },
        "gov.irs.social_security.taxability.threshold.base.main.HEAD_OF_HOUSEHOLD": {
            "2026-01-01.2100-12-31": 0
        },
        # Set all adjusted base thresholds to 0
        "gov.irs.social_security.taxability.threshold.adjusted_base.main.JOINT": {
            "2026-01-01.2100-12-31": 0
        },
        "gov.irs.social_security.taxability.threshold.adjusted_base.main.SINGLE": {
            "2026-01-01.2100-12-31": 0
        },
        "gov.irs.social_security.taxability.threshold.adjusted_base.main.SEPARATE": {
            "2026-01-01.2100-12-31": 0
        },
        "gov.irs.social_security.taxability.threshold.adjusted_base.main.SURVIVING_SPOUSE": {
            "2026-01-01.2100-12-31": 0
        },
        "gov.irs.social_security.taxability.threshold.adjusted_base.main.HEAD_OF_HOUSEHOLD": {
            "2026-01-01.2100-12-31": 0
        }
    }


def tax_100_percent_ss():
    """Tax 100% of Social Security benefits for all recipients.

    This reform makes 100% of Social Security benefits taxable regardless
    of income level, extending beyond the current 85% maximum.

    Sets all rate parameters to 1.0 with all thresholds at zero.
    """
    return {
        # Set combined income fraction to 1.0
        "gov.irs.social_security.taxability.combined_income_ss_fraction": {
            "2026-01-01.2100-12-31": 1.0
        },
        # Set all base thresholds to 0
        "gov.irs.social_security.taxability.threshold.base.main.JOINT": {
            "2026-01-01.2100-12-31": 0
        },
        "gov.irs.social_security.taxability.threshold.base.main.SINGLE": {
            "2026-01-01.2100-12-31": 0
        },
        "gov.irs.social_security.taxability.threshold.base.main.SEPARATE": {
            "2026-01-01.2100-12-31": 0
        },
        "gov.irs.social_security.taxability.threshold.base.main.SURVIVING_SPOUSE": {
            "2026-01-01.2100-12-31": 0
        },
        "gov.irs.social_security.taxability.threshold.base.main.HEAD_OF_HOUSEHOLD": {
            "2026-01-01.2100-12-31": 0
        },
        # Set all adjusted base thresholds to 0
        "gov.irs.social_security.taxability.threshold.adjusted_base.main.JOINT": {
            "2026-01-01.2100-12-31": 0
        },
        "gov.irs.social_security.taxability.threshold.adjusted_base.main.SINGLE": {
            "2026-01-01.2100-12-31": 0
        },
        "gov.irs.social_security.taxability.threshold.adjusted_base.main.SEPARATE": {
            "2026-01-01.2100-12-31": 0
        },
        "gov.irs.social_security.taxability.threshold.adjusted_base.main.SURVIVING_SPOUSE": {
            "2026-01-01.2100-12-31": 0
        },
        "gov.irs.social_security.taxability.threshold.adjusted_base.main.HEAD_OF_HOUSEHOLD": {
            "2026-01-01.2100-12-31": 0
        },
        # Set all rate parameters to 1.0 for 100% taxation
        "gov.irs.social_security.taxability.rate.base.benefit_cap": {
            "2026-01-01.2100-12-31": 1.0
        },
        "gov.irs.social_security.taxability.rate.base.excess": {
            "2026-01-01.2100-12-31": 1.0
        },
        "gov.irs.social_security.taxability.rate.additional.benefit_cap": {
            "2026-01-01.2100-12-31": 1.0
        },
        "gov.irs.social_security.taxability.rate.additional.excess": {
            "2026-01-01.2100-12-31": 1.0
        },
        "gov.irs.social_security.taxability.rate.additional.bracket": {
            "2026-01-01.2100-12-31": 1.0
        }
    }


def eliminate_senior_deduction():
    """Eliminate the bonus senior deduction."""
    return {
        "gov.irs.deductions.senior_deduction.amount": {
            "2026-01-01.2100-12-31": 0
        }
    }


def extend_senior_deduction():
    """Permanently extend the senior deduction."""
    return {
        "gov.contrib.crfb.senior_deduction_extension.applies": {
            "2026-01-01.2100-12-31": True
        }
    }


def add_ss_tax_credit(amount, filing_statuses=None):
    """Add a Social Security tax credit.

    Args:
        amount: Credit amount in dollars
        filing_statuses: List of filing statuses to apply credit to
                        (default: all statuses)
    """
    if filing_statuses is None:
        filing_statuses = ["JOINT", "SINGLE", "SEPARATE", "SURVIVING_SPOUSE", "HEAD_OF_HOUSEHOLD"]

    credit_params = {
        "gov.contrib.crfb.ss_credit.in_effect": {
            "2026-01-01.2100-12-31": True
        }
    }

    for status in filing_statuses:
        credit_params[f"gov.contrib.crfb.ss_credit.amount.{status}"] = {
            "2026-01-01.2100-12-31": amount
        }

    return credit_params


def enable_employer_payroll_tax(percentage=1.0):
    """Enable taxation of employer payroll contributions.

    Args:
        percentage: Fraction of employer payroll tax to include (0.0 to 1.0)
    """
    return {
        "gov.contrib.crfb.tax_employer_payroll_tax.in_effect": {
            "2026-01-01.2100-12-31": True
        },
        "gov.contrib.crfb.tax_employer_payroll_tax.percentage": {
            "2026-01-01.2100-12-31": percentage
        }
    }


# Policy reform functions using modular components

def get_option1_reform():
    """Option 1: Full Repeal of Social Security Benefits Taxation.

    Completely eliminates federal income taxation of Social Security benefits,
    returning to the pre-1984 policy where benefits were not subject to income tax.
    """
    return Reform.from_dict(eliminate_ss_taxation(), country_id="us")


def get_option2_reform():
    """Option 2: Taxation of 85% of Social Security Benefits.

    Taxes 85% of Social Security benefits for all recipients,
    regardless of income level, eliminating the current threshold system.
    """
    return Reform.from_dict(tax_85_percent_ss(), country_id="us")


def get_option3_reform():
    """Option 3: 85% Taxation with Permanent Senior Deduction Extension.

    Combines taxation of 85% of benefits with a permanent extension
    of the senior deduction that would otherwise expire in 2028.
    """
    # Combine parametric SS reform with senior deduction extension
    return Reform.from_dict({
        **tax_85_percent_ss(),
        **extend_senior_deduction()
    }, country_id="us")


def get_option4_reform(credit_amount=500):
    """Option 4: Social Security Tax Credit System.

    Replaces the senior deduction with a nonrefundable tax credit
    while taxing 85% of benefits.

    Args:
        credit_amount: The credit amount in dollars (default: 500)
    """
    # Combine parametric SS reform with credit and deduction changes
    return Reform.from_dict({
        **tax_85_percent_ss(),
        **add_ss_tax_credit(credit_amount),
        **eliminate_senior_deduction()
    }, country_id="us")


def get_option5_reform():
    """Option 5: Roth-Style Swap.

    Eliminates Social Security benefit taxation while making
    employer payroll contributions taxable income.
    """
    return Reform.from_dict({
        **eliminate_ss_taxation(),
        **enable_employer_payroll_tax(1.0)
    }, country_id="us")


def get_option6_reform():
    """Option 6: Phased Roth-Style Swap.

    Implements a gradual transition to the Roth-style system over multiple years,
    phasing in employer contribution taxation while phasing out benefit taxation.
    """
    reform_dict = {
        # Enable employer payroll tax inclusion
        "gov.contrib.crfb.tax_employer_payroll_tax.in_effect": {
            "2026-01-01.2100-12-31": True
        },
        # Phase in employer payroll tax (1% per year from 2026 to 2033)
        "gov.contrib.crfb.tax_employer_payroll_tax.percentage": {
            "2026-01-01.2026-12-31": 0.1307,  # 1/7.65
            "2027-01-01.2027-12-31": 0.2614,  # 2/7.65
            "2028-01-01.2028-12-31": 0.3922,  # 3/7.65
            "2029-01-01.2029-12-31": 0.5229,  # 4/7.65
            "2030-01-01.2030-12-31": 0.6536,  # 5/7.65
            "2031-01-01.2031-12-31": 0.7843,  # 6/7.65
            "2032-01-01.2032-12-31": 0.9150,  # 7/7.65
            "2033-01-01.2100-12-31": 1.0      # Full amount
        },
        # Phase down Social Security benefits taxation starting 2029
        # Base rate starts at 50%, decreases by 5% per year
        "gov.irs.social_security.taxability.rate.base": {
            "2029-01-01.2029-12-31": 0.45,
            "2030-01-01.2030-12-31": 0.40,
            "2031-01-01.2031-12-31": 0.35,
            "2032-01-01.2032-12-31": 0.30,
            "2033-01-01.2033-12-31": 0.25,
            "2034-01-01.2034-12-31": 0.20,
            "2035-01-01.2035-12-31": 0.15,
            "2036-01-01.2036-12-31": 0.10,
            "2037-01-01.2037-12-31": 0.05,
            "2038-01-01.2100-12-31": 0
        },
        # Additional rate starts at 85%, decreases by 5% per year until 35%
        "gov.irs.social_security.taxability.rate.additional": {
            "2029-01-01.2029-12-31": 0.80,
            "2030-01-01.2030-12-31": 0.75,
            "2031-01-01.2031-12-31": 0.70,
            "2032-01-01.2032-12-31": 0.65,
            "2033-01-01.2033-12-31": 0.60,
            "2034-01-01.2034-12-31": 0.55,
            "2035-01-01.2035-12-31": 0.50,
            "2036-01-01.2036-12-31": 0.45,
            "2037-01-01.2037-12-31": 0.40,
            "2038-01-01.2038-12-31": 0.35,
            "2039-01-01.2039-12-31": 0.30,
            "2040-01-01.2040-12-31": 0.25,
            "2041-01-01.2041-12-31": 0.20,
            "2042-01-01.2042-12-31": 0.15,
            "2043-01-01.2043-12-31": 0.10,
            "2044-01-01.2044-12-31": 0.05,
            "2045-01-01.2100-12-31": 0
        }
    }

    return Reform.from_dict(reform_dict, country_id="us")


def get_option7_reform():
    """Option 7: Eliminate Bonus Senior Deduction.

    Eliminates the $6,000 bonus senior deduction from the One Big Beautiful Bill
    that has a 6% phase-out beginning at $75k/$150k for single/joint filers.
    The deduction expires in 2029, so there's only impact from 2026-2028.
    """
    return Reform.from_dict(eliminate_senior_deduction(), country_id="us")


def get_option8_reform():
    """Option 8: Full Taxation of Social Security Benefits.

    Makes 100% of Social Security benefits taxable for all recipients,
    regardless of income level. This is more comprehensive than Option 2
    which taxes only 85% of benefits.
    """
    return Reform.from_dict(tax_100_percent_ss(), country_id="us")


# Dictionary mapping reform IDs to configurations
REFORMS = {
    "option1": {
        "name": "Full Repeal of Social Security Benefits Taxation",
        "func": get_option1_reform,
    },
    "option2": {
        "name": "Taxation of 85% of Social Security Benefits",
        "func": get_option2_reform,
    },
    "option3": {
        "name": "85% Taxation with Permanent Senior Deduction Extension",
        "func": get_option3_reform,
    },
    "option4": {
        "name": "Social Security Tax Credit System ($500)",
        "func": get_option4_reform,
    },
    "option5": {
        "name": "Roth-Style Swap",
        "func": get_option5_reform,
    },
    "option6": {
        "name": "Phased Roth-Style Swap",
        "func": get_option6_reform,
    },
    "option7": {
        "name": "Eliminate Bonus Senior Deduction",
        "func": get_option7_reform,
    },
    "option8": {
        "name": "Full Taxation of Social Security Benefits",
        "func": get_option8_reform,
    },
}
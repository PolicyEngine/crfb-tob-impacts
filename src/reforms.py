"""
Policy reform definitions for Social Security taxation analysis.

This module contains functions that return Reform objects for different
Social Security taxation policy options.
"""

from policyengine_core.reforms import Reform


def get_option1_reform():
    """Option 1: Full Repeal of Social Security Benefits Taxation.

    Completely eliminates federal income taxation of Social Security benefits,
    returning to the pre-1984 policy where benefits were not subject to income tax.
    """
    return Reform.from_dict({
        "gov.irs.social_security.taxability.rate.base": {
            "2026-01-01.2100-12-31": 0
        },
        "gov.irs.social_security.taxability.rate.additional": {
            "2026-01-01.2100-12-31": 0
        }
    }, country_id="us")


def get_option2_reform():
    """Option 2: Taxation of 85% of Social Security Benefits.

    Taxes 85% of Social Security benefits for all recipients,
    regardless of income level, eliminating the current threshold system.
    """
    return Reform.from_dict({
        "gov.irs.social_security.taxability.rate.base": {
            "2026-01-01.2100-12-31": 0.85
        },
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
    }, country_id="us")


def get_option3_reform():
    """Option 3: 85% Taxation with Permanent Senior Deduction Extension.

    Combines taxation of 85% of benefits with a permanent extension
    of the senior deduction that would otherwise expire in 2028.
    """
    return Reform.from_dict({
        "gov.irs.social_security.taxability.rate.base": {
            "2026-01-01.2100-12-31": 0.85
        },
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
        "gov.contrib.crfb.senior_deduction_extension.applies": {
            "2026-01-01.2100-12-31": True
        }
    }, country_id="us")


def get_option4_reform(credit_amount=500):
    """Option 4: Social Security Tax Credit System.

    Replaces the senior deduction with a nonrefundable tax credit
    while taxing 85% of benefits.

    Args:
        credit_amount: The credit amount in dollars (default: 500)
    """
    return Reform.from_dict({
        "gov.irs.social_security.taxability.rate.base": {
            "2026-01-01.2100-12-31": 0.85
        },
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
        "gov.contrib.crfb.ss_credit.in_effect": {
            "2026-01-01.2100-12-31": True
        },
        "gov.contrib.crfb.ss_credit.amount.JOINT": {
            "2026-01-01.2100-12-31": credit_amount
        },
        "gov.contrib.crfb.ss_credit.amount.SINGLE": {
            "2026-01-01.2100-12-31": credit_amount
        },
        "gov.contrib.crfb.ss_credit.amount.SEPARATE": {
            "2026-01-01.2100-12-31": credit_amount
        },
        "gov.contrib.crfb.ss_credit.amount.SURVIVING_SPOUSE": {
            "2026-01-01.2100-12-31": credit_amount
        },
        "gov.contrib.crfb.ss_credit.amount.HEAD_OF_HOUSEHOLD": {
            "2026-01-01.2100-12-31": credit_amount
        },
        "gov.irs.deductions.senior_deduction.amount": {
            "2026-01-01.2100-12-31": 0
        }
    }, country_id="us")


def get_option5_reform():
    """Option 5: Roth-Style Swap.

    Eliminates Social Security benefit taxation while making
    employer payroll contributions taxable income.
    """
    return Reform.from_dict({
        "gov.irs.social_security.taxability.rate.base": {
            "2026-01-01.2100-12-31": 0
        },
        "gov.irs.social_security.taxability.rate.additional": {
            "2026-01-01.2100-12-31": 0
        },
        "gov.contrib.crfb.tax_employer_payroll_tax.in_effect": {
            "2026-01-01.2100-12-31": True
        },
        "gov.contrib.crfb.tax_employer_payroll_tax.percentage": {
            "2026-01-01.2100-12-31": 1.0
        }
    }, country_id="us")


def get_option6_reform():
    """Option 6: Phased Roth-Style Swap.

    Implements a gradual transition to the Roth-style system over multiple years,
    phasing in employer contribution taxation while phasing out benefit taxation.
    """
    reform_dict = {
        "gov.contrib.crfb.tax_employer_payroll_tax.in_effect": {
            "2026-01-01.2100-12-31": True
        },
        "gov.contrib.crfb.tax_employer_payroll_tax.percentage": {
            "2026-01-01.2026-12-31": 0.1307,
            "2027-01-01.2027-12-31": 0.2614,
            "2028-01-01.2028-12-31": 0.3922,
            "2029-01-01.2029-12-31": 0.5229,
            "2030-01-01.2030-12-31": 0.6536,
            "2031-01-01.2031-12-31": 0.7843,
            "2032-01-01.2032-12-31": 0.9150,
            "2033-01-01.2100-12-31": 1.0
        },
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
    return Reform.from_dict({
        "gov.irs.deductions.senior_deduction.amount": {
            "2026-01-01.2100-12-31": 0
        }
    }, country_id="us")


# Registry of all reforms for easy access
REFORMS = {
    "option1": {
        "name": "Full Repeal of Social Security Benefits Taxation",
        "func": get_option1_reform,
        "has_variants": False
    },
    "option2": {
        "name": "Taxation of 85% of Social Security Benefits",
        "func": get_option2_reform,
        "has_variants": False
    },
    "option3": {
        "name": "85% Taxation with Permanent Senior Deduction Extension",
        "func": get_option3_reform,
        "has_variants": False
    },
    "option4": {
        "name": "Social Security Tax Credit System",
        "func": get_option4_reform,
        "has_variants": True,
        "variants": [100, 200, 300, 400, 500, 600, 700, 800, 900]
    },
    "option5": {
        "name": "Roth-Style Swap",
        "func": get_option5_reform,
        "has_variants": False
    },
    "option6": {
        "name": "Phased Roth-Style Swap",
        "func": get_option6_reform,
        "has_variants": False
    },
    "option7": {
        "name": "Eliminate Bonus Senior Deduction",
        "func": get_option7_reform,
        "has_variants": False
    }
}
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
    """Eliminate Social Security benefit taxation.

    Sets all SS taxation rate parameters to 0 to completely eliminate
    federal income taxation of Social Security benefits.
    """
    return {
        # Base rate parameters (0-50% bracket)
        "gov.irs.social_security.taxability.rate.base.benefit_cap": {
            "2026-01-01.2100-12-31": 0
        },
        "gov.irs.social_security.taxability.rate.base.excess": {
            "2026-01-01.2100-12-31": 0
        },
        # Additional rate parameters (50-85% bracket)
        "gov.irs.social_security.taxability.rate.additional.benefit_cap": {
            "2026-01-01.2100-12-31": 0
        },
        "gov.irs.social_security.taxability.rate.additional.bracket": {
            "2026-01-01.2100-12-31": 0
        },
        "gov.irs.social_security.taxability.rate.additional.excess": {
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


def tax_90_percent_ss():
    """Tax 90% of Social Security benefits for all recipients.

    This reform makes 90% of Social Security benefits taxable regardless
    of income level, slightly above the current 85% maximum.

    Sets all rate parameters to 0.90 with all thresholds at zero.
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
        # Set all rate parameters to 0.90 for 90% taxation
        "gov.irs.social_security.taxability.rate.base.benefit_cap": {
            "2026-01-01.2100-12-31": 0.90
        },
        "gov.irs.social_security.taxability.rate.base.excess": {
            "2026-01-01.2100-12-31": 0.90
        },
        "gov.irs.social_security.taxability.rate.additional.benefit_cap": {
            "2026-01-01.2100-12-31": 0.90
        },
        "gov.irs.social_security.taxability.rate.additional.excess": {
            "2026-01-01.2100-12-31": 0.90
        },
        "gov.irs.social_security.taxability.rate.additional.bracket": {
            "2026-01-01.2100-12-31": 0.90
        }
    }


def tax_95_percent_ss():
    """Tax 95% of Social Security benefits for all recipients.

    This reform makes 95% of Social Security benefits taxable regardless
    of income level, above the current 85% maximum but below 100%.

    Sets all rate parameters to 0.95 with all thresholds at zero.
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
        # Set all rate parameters to 0.95 for 95% taxation
        "gov.irs.social_security.taxability.rate.base.benefit_cap": {
            "2026-01-01.2100-12-31": 0.95
        },
        "gov.irs.social_security.taxability.rate.base.excess": {
            "2026-01-01.2100-12-31": 0.95
        },
        "gov.irs.social_security.taxability.rate.additional.benefit_cap": {
            "2026-01-01.2100-12-31": 0.95
        },
        "gov.irs.social_security.taxability.rate.additional.excess": {
            "2026-01-01.2100-12-31": 0.95
        },
        "gov.irs.social_security.taxability.rate.additional.bracket": {
            "2026-01-01.2100-12-31": 0.95
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


def enable_ss_credit_phase_out():
    """Enable the phase-out for the SS nonrefundable credit.

    Phase-out rates (from policyengine-us PR #7089):
    - Joint filers: 6% phase-out rate for AGI above $150,000
    - Other filers: 6% phase-out rate for AGI above $75,000
    """
    return {
        "gov.contrib.crfb.ss_credit.phase_out.applies": {
            "2026-01-01.2100-12-31": True
        }
    }


# CBO labor supply elasticities (for dynamic scoring)
CBO_ELASTICITIES = {
    "gov.simulation.labor_supply_responses.elasticities.income.all": {
        "2024-01-01.2100-12-31": -0.05
    },
    "gov.simulation.labor_supply_responses.elasticities.substitution.by_position_and_decile.primary.1": {
        "2024-01-01.2100-12-31": 0.31
    },
    "gov.simulation.labor_supply_responses.elasticities.substitution.by_position_and_decile.primary.2": {
        "2024-01-01.2100-12-31": 0.28
    },
    "gov.simulation.labor_supply_responses.elasticities.substitution.by_position_and_decile.primary.3": {
        "2024-01-01.2100-12-31": 0.27
    },
    "gov.simulation.labor_supply_responses.elasticities.substitution.by_position_and_decile.primary.4": {
        "2024-01-01.2100-12-31": 0.27
    },
    "gov.simulation.labor_supply_responses.elasticities.substitution.by_position_and_decile.primary.5": {
        "2024-01-01.2100-12-31": 0.25
    },
    "gov.simulation.labor_supply_responses.elasticities.substitution.by_position_and_decile.primary.6": {
        "2024-01-01.2100-12-31": 0.25
    },
    "gov.simulation.labor_supply_responses.elasticities.substitution.by_position_and_decile.primary.7": {
        "2024-01-01.2100-12-31": 0.22
    },
    "gov.simulation.labor_supply_responses.elasticities.substitution.by_position_and_decile.primary.8": {
        "2024-01-01.2100-12-31": 0.19
    },
    "gov.simulation.labor_supply_responses.elasticities.substitution.by_position_and_decile.primary.9": {
        "2024-01-01.2100-12-31": 0.15
    },
    "gov.simulation.labor_supply_responses.elasticities.substitution.by_position_and_decile.primary.10": {
        "2024-01-01.2100-12-31": 0.10
    }
}


# Dict-returning functions for each option (used for dynamic scoring)
# These return complete parameter dictionaries with CBO elasticities pre-merged

def get_option1_dict():
    """Return parameter dict for Option 1 (static scoring only - no elasticities)."""
    return eliminate_ss_taxation()

def get_option2_dict():
    """Return parameter dict for Option 2 (static scoring only - no elasticities)."""
    return tax_85_percent_ss()

def get_option3_dict():
    """Return parameter dict for Option 3 (static scoring only - no elasticities)."""
    result = {}
    result.update(tax_85_percent_ss())
    result.update(extend_senior_deduction())
    return result

def get_option4_dict(credit_amount=500):
    """Return parameter dict for Option 4 (static scoring only - no elasticities)."""
    result = {}
    result.update(tax_85_percent_ss())
    result.update(add_ss_tax_credit(credit_amount))
    result.update(eliminate_senior_deduction())
    return result

def get_option5_dict():
    """Return parameter dict for Option 5 (static scoring only - no elasticities)."""
    result = {}
    result.update(eliminate_ss_taxation())
    result.update(enable_employer_payroll_tax(1.0))
    return result

def get_option6_dict():
    """Return parameter dict for Option 6 (static scoring only - no elasticities)."""
    reform_dict = {
        "gov.contrib.crfb.tax_employer_payroll_tax.in_effect": {
            "2026-01-01.2100-12-31": True
        },
        "gov.contrib.crfb.tax_employer_payroll_tax.percentage": {
            "2026": 0.1307,
            "2027": 0.2614,
            "2028": 0.3922,
            "2029": 0.5229,
            "2030": 0.6536,
            "2031": 0.7843,
            "2032": 0.9150,
            "2033-01-01.2100-12-31": 1.0
        },
    }

    # Phase down base rate parameters
    base_years = [2029, 2030, 2031, 2032, 2033, 2034, 2035, 2036, 2037]
    base_values = [0.45, 0.40, 0.35, 0.30, 0.25, 0.20, 0.15, 0.10, 0.05]

    for param_name in ["benefit_cap", "excess"]:
        param_path = f"gov.irs.social_security.taxability.rate.base.{param_name}"
        reform_dict[param_path] = {}
        for year, value in zip(base_years, base_values):
            reform_dict[param_path][str(year)] = value
        reform_dict[param_path]["2038-01-01.2100-12-31"] = 0

    # Phase down additional rate parameters
    add_years = list(range(2029, 2045))
    add_values = [0.80, 0.75, 0.70, 0.65, 0.60, 0.55, 0.50, 0.45, 0.40,
                  0.35, 0.30, 0.25, 0.20, 0.15, 0.10, 0.05]

    for param_name in ["benefit_cap", "bracket", "excess"]:
        param_path = f"gov.irs.social_security.taxability.rate.additional.{param_name}"
        reform_dict[param_path] = {}
        for year, value in zip(add_years, add_values):
            reform_dict[param_path][str(year)] = value
        reform_dict[param_path]["2045-01-01.2100-12-31"] = 0

    return reform_dict

def get_option7_dict():
    """Return parameter dict for Option 7 (static scoring only - no elasticities)."""
    return eliminate_senior_deduction()

def get_option8_dict():
    """Return parameter dict for Option 8 (static scoring only - no elasticities)."""
    return tax_100_percent_ss()

def get_option9_dict():
    """Return parameter dict for Option 9 (static scoring only - no elasticities)."""
    return tax_90_percent_ss()

def get_option10_dict():
    """Return parameter dict for Option 10 (static scoring only - no elasticities)."""
    return tax_95_percent_ss()

def get_option11_dict():
    """Return parameter dict for Option 11 (static scoring only - no elasticities).

    $700 credit with 6% phase-out above $150k (joint) / $75k (other).
    """
    result = {}
    result.update(tax_85_percent_ss())
    result.update(add_ss_tax_credit(700))
    result.update(enable_ss_credit_phase_out())
    result.update(eliminate_senior_deduction())
    return result

def get_option12_dict():
    """Return parameter dict for Option 12 (static scoring only - no elasticities).

    Extended Roth-Style Swap with specific phase-out schedule:
    - Employer payroll tax: 100% immediately (2026+)
    - Benefit taxation phase-out at 2.5%/year using TRUST FUND ALLOCATION:
      - Phase 1 (2029-2048): OASDI portion phases out
        - oasdi_share_of_gross_ss: 0.5 → 0 (controls trust fund split)
        - base rates: 0.50 → 0 (tier 1 people stop paying TOB)
        - additional rates: 0.85 → 0.35 (tier 2 people keep paying HI portion)
      - Phase 2 (2049-2062): Medicare HI portion phases out
        - additional rates: 0.35 → 0

    Key insight: oasdi_share_of_gross_ss controls how TOB revenue is SPLIT between
    OASDI and HI trust funds via branching calculation. Reducing it alongside
    taxability rates ensures OASDI goes to zero while HI stays approximately constant.
    """
    # Phase-out schedule constants
    ANNUAL_PHASE_OUT_RATE = 0.025  # 2.5% per year
    INITIAL_OASDI_SHARE = 0.50     # Starting OASDI share of gross SS taxation
    INITIAL_BASE_RATE = 0.50       # Starting base taxability rate (tier 1)
    INITIAL_ADDITIONAL_RATE = 0.85 # Starting additional taxability rate (tier 2)
    HI_ONLY_RATE = 0.35            # Rate after OASDI phased out (HI portion only)
    PHASE1_YEARS_COUNT = 20        # Years to phase out OASDI (2029-2048)
    PHASE2_YEARS_COUNT = 14        # Years to phase out HI (2049-2062)

    reform_dict = {
        # Immediate employer payroll taxation (100% from 2026)
        "gov.contrib.crfb.tax_employer_payroll_tax.in_effect": {
            "2026-01-01.2100-12-31": True
        },
        "gov.contrib.crfb.tax_employer_payroll_tax.percentage": {
            "2026-01-01.2100-12-31": 1.0
        },
    }

    # Phase 1: Phase out OASDI portion over 2029-2048
    phase1_years = list(range(2029, 2029 + PHASE1_YEARS_COUNT))

    # 1. oasdi_share_of_gross_ss: 0.5 → 0 (controls trust fund allocation)
    oasdi_share_values = [INITIAL_OASDI_SHARE - ANNUAL_PHASE_OUT_RATE * (i + 1) for i in range(PHASE1_YEARS_COUNT)]
    reform_dict["gov.ssa.revenue.oasdi_share_of_gross_ss"] = {}
    for year, value in zip(phase1_years, oasdi_share_values):
        reform_dict["gov.ssa.revenue.oasdi_share_of_gross_ss"][str(year)] = round(value, 4)
    reform_dict["gov.ssa.revenue.oasdi_share_of_gross_ss"]["2049-01-01.2100-12-31"] = 0

    # 2. base rates: 0.50 → 0 (tier 1 people phase out of TOB entirely)
    base_values = [INITIAL_BASE_RATE - ANNUAL_PHASE_OUT_RATE * (i + 1) for i in range(PHASE1_YEARS_COUNT)]
    for param_name in ["benefit_cap", "excess"]:
        param_path = f"gov.irs.social_security.taxability.rate.base.{param_name}"
        reform_dict[param_path] = {}
        for year, value in zip(phase1_years, base_values):
            reform_dict[param_path][str(year)] = round(value, 4)
        reform_dict[param_path]["2049-01-01.2100-12-31"] = 0

    # 3. additional rates: 0.85 → 0.35 (tier 2 people keep paying HI portion)
    # Formula: additional = oasdi_share + HI_ONLY_RATE, so as oasdi_share → 0, additional → HI_ONLY_RATE
    additional_values = [INITIAL_ADDITIONAL_RATE - ANNUAL_PHASE_OUT_RATE * (i + 1) for i in range(PHASE1_YEARS_COUNT)]
    for param_name in ["benefit_cap", "excess"]:
        param_path = f"gov.irs.social_security.taxability.rate.additional.{param_name}"
        reform_dict[param_path] = {}
        for year, value in zip(phase1_years, additional_values):
            reform_dict[param_path][str(year)] = round(value, 4)
        # Will be overwritten by Phase 2 values below

    # Phase 2: Phase out HI portion over 2049-2062
    phase2_start = 2029 + PHASE1_YEARS_COUNT  # 2049
    phase2_years = list(range(phase2_start, phase2_start + PHASE2_YEARS_COUNT))
    hi_values = [HI_ONLY_RATE - ANNUAL_PHASE_OUT_RATE * (i + 1) for i in range(PHASE2_YEARS_COUNT)]

    for param_name in ["benefit_cap", "excess"]:
        param_path = f"gov.irs.social_security.taxability.rate.additional.{param_name}"
        for year, value in zip(phase2_years, hi_values):
            reform_dict[param_path][str(year)] = round(value, 4)
        reform_dict[param_path]["2063-01-01.2100-12-31"] = 0

    return reform_dict


# Complete dynamic scoring dictionaries with CBO elasticities pre-merged
def get_option1_dynamic_dict():
    """Return complete parameter dict for Option 1 with CBO elasticities."""
    result = {}
    result.update(eliminate_ss_taxation())
    result.update(CBO_ELASTICITIES)
    return result

def get_option2_dynamic_dict():
    """Return complete parameter dict for Option 2 with CBO elasticities."""
    result = {}
    result.update(tax_85_percent_ss())
    result.update(CBO_ELASTICITIES)
    return result

def get_option3_dynamic_dict():
    """Return complete parameter dict for Option 3 with CBO elasticities."""
    result = {}
    result.update(tax_85_percent_ss())
    result.update(extend_senior_deduction())
    result.update(CBO_ELASTICITIES)
    return result

def get_option4_dynamic_dict(credit_amount=500):
    """Return complete parameter dict for Option 4 with CBO elasticities."""
    result = {}
    result.update(tax_85_percent_ss())
    result.update(add_ss_tax_credit(credit_amount))
    result.update(eliminate_senior_deduction())
    result.update(CBO_ELASTICITIES)
    return result

def get_option5_dynamic_dict():
    """Return complete parameter dict for Option 5 with CBO elasticities."""
    result = {}
    result.update(eliminate_ss_taxation())
    result.update(enable_employer_payroll_tax(1.0))
    result.update(CBO_ELASTICITIES)
    return result

def get_option6_dynamic_dict():
    """Return complete parameter dict for Option 6 with CBO elasticities."""
    reform_dict = {
        "gov.contrib.crfb.tax_employer_payroll_tax.in_effect": {
            "2026-01-01.2100-12-31": True
        },
        "gov.contrib.crfb.tax_employer_payroll_tax.percentage": {
            "2026": 0.1307,
            "2027": 0.2614,
            "2028": 0.3922,
            "2029": 0.5229,
            "2030": 0.6536,
            "2031": 0.7843,
            "2032": 0.9150,
            "2033-01-01.2100-12-31": 1.0
        },
    }

    # Phase down base rate parameters
    base_years = [2029, 2030, 2031, 2032, 2033, 2034, 2035, 2036, 2037]
    base_values = [0.45, 0.40, 0.35, 0.30, 0.25, 0.20, 0.15, 0.10, 0.05]

    for param_name in ["benefit_cap", "excess"]:
        param_path = f"gov.irs.social_security.taxability.rate.base.{param_name}"
        reform_dict[param_path] = {}
        for year, value in zip(base_years, base_values):
            reform_dict[param_path][str(year)] = value
        reform_dict[param_path]["2038-01-01.2100-12-31"] = 0

    # Phase down additional rate parameters
    add_years = list(range(2029, 2045))
    add_values = [0.80, 0.75, 0.70, 0.65, 0.60, 0.55, 0.50, 0.45, 0.40,
                  0.35, 0.30, 0.25, 0.20, 0.15, 0.10, 0.05]

    for param_name in ["benefit_cap", "bracket", "excess"]:
        param_path = f"gov.irs.social_security.taxability.rate.additional.{param_name}"
        reform_dict[param_path] = {}
        for year, value in zip(add_years, add_values):
            reform_dict[param_path][str(year)] = value
        reform_dict[param_path]["2045-01-01.2100-12-31"] = 0

    # Add CBO elasticities
    reform_dict.update(CBO_ELASTICITIES)
    return reform_dict

def get_option7_dynamic_dict():
    """Return complete parameter dict for Option 7 with CBO elasticities."""
    result = {}
    result.update(eliminate_senior_deduction())
    result.update(CBO_ELASTICITIES)
    return result

def get_option8_dynamic_dict():
    """Return complete parameter dict for Option 8 with CBO elasticities."""
    result = {}
    result.update(tax_100_percent_ss())
    result.update(CBO_ELASTICITIES)
    return result

def get_option9_dynamic_dict():
    """Return complete parameter dict for Option 9 with CBO elasticities."""
    result = {}
    result.update(tax_90_percent_ss())
    result.update(CBO_ELASTICITIES)
    return result

def get_option10_dynamic_dict():
    """Return complete parameter dict for Option 10 with CBO elasticities."""
    result = {}
    result.update(tax_95_percent_ss())
    result.update(CBO_ELASTICITIES)
    return result

def get_option11_dynamic_dict():
    """Return complete parameter dict for Option 11 with CBO elasticities.

    $700 credit with 6% phase-out above $150k (joint) / $75k (other).
    """
    result = {}
    result.update(tax_85_percent_ss())
    result.update(add_ss_tax_credit(700))
    result.update(enable_ss_credit_phase_out())
    result.update(eliminate_senior_deduction())
    result.update(CBO_ELASTICITIES)
    return result

def get_option12_dynamic_dict():
    """Return complete parameter dict for Option 12 with CBO elasticities.

    Extended Roth-Style Swap with specific phase-out schedule.
    """
    result = get_option12_dict()
    result.update(CBO_ELASTICITIES)
    return result


# =============================================================================
# OPTION 13 / BALANCED FIX - NOT IMPLEMENTED HERE
# =============================================================================
#
# Option 13 (Balanced Fix Baseline) requires dynamic year-by-year gap closing
# that CANNOT be implemented via Reform.from_dict(). The implementation requires:
#
#   1. Running a baseline simulation to calculate actual SS/HI gaps each year
#   2. Computing tax rate increases dynamically based on real gaps
#   3. Applying benefit cuts via set_input() with TOB feedback adjustment
#
# The correct implementation is in: batch/run_option13_modal.py
#
# Gap Closing Formula (per year):
#   - SS Gap = (employee_ss_tax + employer_ss_tax + tob_oasdi) - ss_benefits
#   - HI Gap = (employee_hi_tax + employer_hi_tax + tob_hi) - medicare_expenditures
#   - 50% closed via payroll tax increases (split employee/employer)
#   - 50% closed via SS benefit cuts (with TOB feedback: cut / (1 - 0.175))
#
# To run Option 13: modal run --detach batch/run_option13_modal.py --years 2035,2036,...
# =============================================================================


# Policy reform functions using modular components

def get_option1_reform():
    """Option 1: Full Repeal of Social Security Benefits Taxation.

    Completely eliminates federal income taxation of Social Security benefits,
    returning to the pre-1984 policy where benefits were not subject to income tax.
    """
    return Reform.from_dict(get_option1_dict(), country_id="us")


def get_option2_reform():
    """Option 2: Taxation of 85% of Social Security Benefits.

    Taxes 85% of Social Security benefits for all recipients,
    regardless of income level, eliminating the current threshold system.
    """
    return Reform.from_dict(get_option2_dict(), country_id="us")


def get_option3_reform():
    """Option 3: 85% Taxation with Permanent Senior Deduction Extension.

    Combines taxation of 85% of benefits with a permanent extension
    of the senior deduction that would otherwise expire in 2028.
    """
    return Reform.from_dict(get_option3_dict(), country_id="us")


def get_option4_reform(credit_amount=500):
    """Option 4: Social Security Tax Credit System.

    Replaces the senior deduction with a nonrefundable tax credit
    while taxing 85% of benefits.

    Args:
        credit_amount: The credit amount in dollars (default: 500)
    """
    return Reform.from_dict(get_option4_dict(credit_amount), country_id="us")


def get_option5_reform():
    """Option 5: Roth-Style Swap.

    Eliminates Social Security benefit taxation while making
    employer payroll contributions taxable income.
    """
    return Reform.from_dict(get_option5_dict(), country_id="us")


def get_option6_reform():
    """Option 6: Phased Roth-Style Swap.

    Implements a gradual transition to the Roth-style system over multiple years,
    phasing in employer contribution taxation while phasing out benefit taxation.

    Note: This reform is complex and may need further refinement for the SS taxation
    phase-down to work properly with PolicyEngine's parameter structure.
    """
    return Reform.from_dict(get_option6_dict(), country_id="us")


def get_option7_reform():
    """Option 7: Eliminate Bonus Senior Deduction.

    Eliminates the $6,000 bonus senior deduction from the One Big Beautiful Bill
    that has a 6% phase-out beginning at $75k/$150k for single/joint filers.
    The deduction expires in 2029, so there's only impact from 2026-2028.
    """
    return Reform.from_dict(get_option7_dict(), country_id="us")


def get_option8_reform():
    """Option 8: Full Taxation of Social Security Benefits.

    Makes 100% of Social Security benefits taxable for all recipients,
    regardless of income level. This is more comprehensive than Option 2
    which taxes only 85% of benefits.
    """
    return Reform.from_dict(get_option8_dict(), country_id="us")


def get_option9_reform():
    """Option 9: Taxation of 90% of Social Security Benefits.

    Makes 90% of Social Security benefits taxable for all recipients,
    regardless of income level. This is above the current 85% maximum
    but below full 100% taxation.
    """
    return Reform.from_dict(get_option9_dict(), country_id="us")


def get_option10_reform():
    """Option 10: Taxation of 95% of Social Security Benefits.

    Makes 95% of Social Security benefits taxable for all recipients,
    regardless of income level. This is above the current 85% maximum
    but below full 100% taxation.
    """
    return Reform.from_dict(get_option10_dict(), country_id="us")


def get_option11_reform():
    """Option 11: $700 Tax Credit with Phase-Out.

    Taxes 85% of Social Security benefits, replaces the senior deduction
    with a $700 nonrefundable credit that phases out at 6% of AGI above
    $150,000 (joint) / $75,000 (other filers).

    Requires policyengine-us with PR #7089 merged.
    """
    return Reform.from_dict(get_option11_dict(), country_id="us")


def get_option12_reform():
    """Option 12: Extended Roth-Style Swap.

    Immediate employer payroll taxation with extended benefit taxation phase-out:
    - 2026+: 100% of employer payroll contributions taxable
    - 2029-2048: OASDI portion (50%) phases out at 2.5%/year
    - 2049-2062: Medicare HI portion (35%) phases out at 2.5%/year
    """
    return Reform.from_dict(get_option12_dict(), country_id="us")


# NOTE: get_option13_reform() and get_balanced_fix_reform() have been removed.
# See comment block above for why Option 13 cannot be implemented here.
# Use batch/run_option13_modal.py instead.


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
    "option9": {
        "name": "Taxation of 90% of Social Security Benefits",
        "func": get_option9_reform,
    },
    "option10": {
        "name": "Taxation of 95% of Social Security Benefits",
        "func": get_option10_reform,
    },
    "option11": {
        "name": "$700 Tax Credit with Phase-Out",
        "func": get_option11_reform,
    },
    "option12": {
        "name": "Extended Roth-Style Swap (2029-2062 Phase-Out)",
        "func": get_option12_reform,
    },
    # NOTE: option13 and balanced_fix removed - use batch/run_option13_modal.py
}
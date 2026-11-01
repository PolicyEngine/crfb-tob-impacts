from __future__ import annotations

from copy import deepcopy


# This manifest defines the CRFB production reform output dataset shape.
# It starts from the current policyengine.py US output dataset variables and
# adds CRFB-specific raw variables needed for later post-H5 aggregation.
#
# Workers calculate it a household chunk at a time, and every cell shares one
# column inventory, so a variable belongs here only if it is numeric, local to
# a household and defined in every scored year. That leaves out race (text),
# medicaid (state cost aggregates), household_income_decile (a population
# rank; aggregation ranks households itself) and the SPM net income and poverty
# variables (the SPM forecast ends in 2035).
DEFAULT_FULL_H5_OUTPUT_VARIABLES_BY_ENTITY: dict[str, list[str]] = {
    "person": [
        "person_id",
        "marital_unit_id",
        "family_id",
        "spm_unit_id",
        "tax_unit_id",
        "household_id",
        "person_weight",
        "age",
        "is_male",
        "is_child",
        "is_adult",
        "employment_income",
        "ssi",
        "social_security",
        "medicare_cost",
        "unemployment_compensation",
        "self_employment_income",
        "partnership_s_corp_income",
        "sstb_self_employment_income_before_lsr",
        "taxable_earnings_for_social_security",
        "social_security_taxable_self_employment_income",
        "employee_social_security_tax",
        "employee_medicare_tax",
        "employer_social_security_tax",
        "employer_medicare_tax",
        "self_employment_tax",
    ],
    "marital_unit": [
        "marital_unit_id",
        "marital_unit_weight",
    ],
    "family": [
        "family_id",
        "family_weight",
    ],
    "spm_unit": [
        "spm_unit_id",
        "spm_unit_weight",
        "snap",
        "tanf",
    ],
    "tax_unit": [
        "tax_unit_id",
        "tax_unit_weight",
        "income_tax",
        "employee_payroll_tax",
        "state_income_tax",
        "household_state_income_tax",
        "eitc",
        "ctc",
        "tax_unit_social_security",
        "tax_unit_taxable_social_security",
        "taxable_social_security",
        "tob_revenue_oasdi",
        "tob_revenue_medicare_hi",
    ],
    "household": [
        "household_id",
        "household_weight",
        "household_count_people",
        "household_net_income",
        "household_benefits",
        "household_tax",
        "household_market_income",
        "congressional_district_geoid",
        "employer_ss_tax_income_tax_revenue",
        "employer_medicare_tax_income_tax_revenue",
    ],
}


TOB_REVENUE_VARIABLES = frozenset(
    {
        "tob_revenue_oasdi",
        "tob_revenue_medicare_hi",
    }
)


def full_h5_output_variable_manifest() -> dict[str, list[str]]:
    return deepcopy(DEFAULT_FULL_H5_OUTPUT_VARIABLES_BY_ENTITY)

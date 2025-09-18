# Policy Options

This chapter describes the six Social Security benefit taxation reform options analyzed in this study. Each option represents a different approach to modifying the current two-tier taxation system, with varying implications for revenue generation, taxpayer burden, and trust fund solvency.

## Current Law Baseline

Under current law, Social Security benefits become subject to federal income taxation when a beneficiary's "combined income" exceeds certain thresholds {cite}`tpc2023ss`. Combined income is defined as adjusted gross income plus nontaxable interest plus half of Social Security benefits.

**Taxation Thresholds (2024):**

**Single filers:**
- $25,000 (50% of benefits taxable)
- $34,000 (85% of benefits taxable)

**Joint filers:**
- $32,000 (50% of benefits taxable)
- $44,000 (85% of benefits taxable)

The revenue generated from this taxation is allocated to the OASI, DI, and HI trust funds based on current law formulas {cite}`ssa2023trustees`.

Additionally, the One Big Beautiful Bill Act included a "bonus senior deduction" of $6,000 for taxpayers aged 65 and older, which expires at the end of 2028 under current law.

## Option 1: Full Repeal of Taxation of Social Security Benefits (No Bonus Senior Deduction After 2028)

**Start Date:** 2026

**Policy Description:** Taxation of Social Security benefits is permanently repealed beginning in 2026. The bonus senior deduction expires at the end of 2028, as per current law.

**Revenue Allocation Impact:** The effect on revenues to the OASDI and HI trust funds will be allocated as per current law. In other words, the revenue that would have been earned by the respective trust funds under current law is the revenue that they will lose under this option.

```{dropdown} Option 1 Reform Code
```python
def get_option1_reform():
    """Option 1: Full Repeal of Social Security Benefits Taxation"""
    return Reform.from_dict({
        "gov.irs.social_security.taxability.rate.base": {
            "2026-01-01.2100-12-31": 0
        },
        "gov.irs.social_security.taxability.rate.additional": {
            "2026-01-01.2100-12-31": 0
        }
    }, country_id="us")
```

**Reform Explanation:** This reform sets both the base and additional Social Security taxability rates to 0%, effectively eliminating all federal income taxation of Social Security benefits starting in 2026. The policy parameters `taxability.rate.base` and `taxability.rate.additional` control the percentage of benefits subject to taxation under the current two-tier system.

## Option 2: Taxation of 85% of Social Security Benefits (No Bonus Senior Deduction After 2028)

**Start Date:** 2026

**Policy Description:** Beginning in 2026, 85% of all Social Security benefits are included in taxable income. The bonus senior deduction expires at the end of 2028, as per current law.

**Revenue Allocation:** The additional revenue from taxation of benefits (TOB) will be allocated to the OASDI and HI trust funds in a way that maintains the current projected shares of TOB revenue earned by the OASI, DI, and HI trust funds.

```{dropdown} Option 2 Reform Code
```python
def get_option2_reform():
    """Option 2: Taxation of 85% of Social Security Benefits"""
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
```

**Reform Explanation:** This reform sets the base taxability rate to 85% and eliminates all income thresholds by setting them to $0 for all filing statuses. This means 85% of all Social Security benefits become taxable income regardless of the recipient's income level, effectively eliminating the current two-tier threshold system.

## Option 3: Taxation of 85% of Social Security Benefits and Permanent Extension of the Bonus Senior Deduction

**Start Date:** 2026

**Policy Description:** Beginning in 2026, 85% of all Social Security benefits are included in taxable income. The bonus senior deduction is permanently extended past 2028.

**Revenue Allocation:** We want to see the full budget estimates for this proposal before deciding how the revenue raised should be allocated across the trust funds because extending the bonus senior deduction will have negative on-budget effects that we will want to incorporate into our decision. Please let us know if you can easily allocate the costs to the general fund onto the trust funds in your model.

```{dropdown} Option 3 Reform Code
```python
def get_option3_reform():
    """Option 3: 85% Taxation with Permanent Senior Deduction Extension"""
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
```

**Reform Explanation:** This reform combines the 85% taxation approach from Option 2 with a permanent extension of the bonus senior deduction. The parameter `senior_deduction_extension.applies` ensures the $6,000 senior deduction continues beyond its scheduled 2028 expiration, partially offsetting the expanded taxation for older taxpayers.

## Option 4: Replace the Bonus Senior Deduction with a Nonrefundable Tax Credit and Tax 85% of All Social Security Benefits

**Start Date:** 2026

**Policy Description:** Beginning in 2026, 85% of all Social Security benefits are included in taxable income. The bonus senior deduction is repealed in 2026 and replaced in the same year by a nonrefundable tax credit made available to all Social Security beneficiaries. The credit can only be applied against taxes owed on Social Security benefits. For the credit's purpose, taxes owed on Social Security will be determined by considering Social Security benefits as a person's "last" income. So if their marginal tax rate is 37%, their last dollar of taxable Social Security income will increase taxes owed by 37 cents.

**Illustrative Example:** An individual with $5,000 in Social Security income and $10,000 in other income facing a 5% tax on income below $10k, a 10% tax on income above that amount, and a $600 nonrefundable credit.

| Taxable Social Security Income | Other Income | Taxes for Determining Credit | Maximum Credit Amount | Credit Received | Taxes Before Credit | Taxes After Credit |
|-------------------------------|--------------|----------------------------|---------------------|-----------------|--------------------|--------------------|
| $5,000 × 85% = $4,250 | $10,000 | $4,250 × 10% = $425 | $600 | MIN(425, 600) = $425 | $925 | $500 |

**Credit Amount:** We are still working to figure out the credit size. We want something that is going to cut taxes as much as the $6,000 deduction for low-income workers but also improve solvency. Let us know if there is something we could iterate; if not, we'll want to decide after we see the results from Option 3.

**Revenue Allocation:** The additional revenue raised will be allocated to the OASDI and HI trust funds in a way that maintains the current projected shares of contributions from TOB revenue to the OASI, DI, and HI trust funds.

```{dropdown} Option 4 Reform Code
```python
def get_option4_reform():
    """Option 4: Social Security Tax Credit System ($500 Credit)"""
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
            "2026-01-01.2100-12-31": 500
        },
        "gov.contrib.crfb.ss_credit.amount.SINGLE": {
            "2026-01-01.2100-12-31": 500
        },
        "gov.contrib.crfb.ss_credit.amount.SEPARATE": {
            "2026-01-01.2100-12-31": 500
        },
        "gov.contrib.crfb.ss_credit.amount.SURVIVING_SPOUSE": {
            "2026-01-01.2100-12-31": 500
        },
        "gov.contrib.crfb.ss_credit.amount.HEAD_OF_HOUSEHOLD": {
            "2026-01-01.2100-12-31": 500
        },
        "gov.irs.deductions.senior_deduction.amount": {
            "2026-01-01.2100-12-31": 0
        }
    }, country_id="us")
```

**Reform Explanation:** This reform implements 85% taxation like Options 2-3 but replaces the bonus senior deduction with a $500 nonrefundable tax credit. The `ss_credit.in_effect` parameter activates the credit system, `ss_credit.amount` sets the credit value for each filing status, and `senior_deduction.amount: 0` eliminates the bonus senior deduction. The credit can only offset taxes owed on Social Security benefits.

## Option 5: Roth-Style Swap: Substitute Income Taxation of Employer Payroll Contributions for Income Taxation of Social Security Benefits

**Start Date:** 2026

**Policy Description:** Beginning in 2026, all employer payroll contributions are included in taxable income and all Social Security benefits are excluded from taxable income. The bonus senior deduction is allowed to expire at the end of 2028, as per current law.

**Revenue Allocation:** Revenue from income taxation of employer Social Security contributions are allocated to the OASDI trust funds. Revenue from income taxation of Medicare contributions are allocated to the HI trust fund. The revenue that would've been earned by the OASDI and HI trust fund from TOB is the revenue that they will lose from the end of TOB.

```{dropdown} Option 5 Reform Code
```python
def get_option5_reform():
    """Option 5: Roth-Style Swap"""
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
```

**Reform Explanation:** This reform implements a "Roth-style swap" by eliminating Social Security benefit taxation (setting rates to 0%) while making employer payroll contributions (7.65% Social Security + Medicare) fully taxable as employee income. The `tax_employer_payroll_tax.percentage: 1.0` parameter means 100% of employer payroll tax contributions become taxable income to the employee.

## Option 6: Phased Roth-Style Swap

**Start Date:** 2026

**Policy Description:** Beginning in 2026, all employer payroll contributions are phased into taxable income by 1 percentage point per year until the full 7.65 percent employer contribution is taxable.

Starting in 2029, the current formula for income taxation of Social Security benefits is phased down by 5 percentage points per year (e.g., 2028: 50/85; 2029: 45/80; 2030: 40/75…, 2038: 0/35; 2039: 0/30…, 2045: 0/0)

The bonus senior deduction is allowed to expire at the end of 2028, as per current law.

**Revenue Allocation During Phase-In:** During the phase-in, the revenue raised from income taxation of employer contributions is allocated to the OASDI trust funds until the contributions included in taxable income exceed the amount contributed to Social Security (6.2%). So, for example, when just 1pp of employer contributions are taxable, the full amount of revenue raised is directed to the OASDI trust fund. When 7pp are included 6.2/7 percent of the revenue is directed to the OASDI trust funds and 0.8/7 percent are directed to the HI trust fund.

When the policy is fully phased in, the revenues are allocated in the same manner as Option 5.

The revenue loss from the phase-out of TOB is allocated to the OASDI and HI trust funds in a way that maintains the current projected shares of TOB revenue earned by the OASI, DI, and HI trust funds.

```{dropdown} Option 6 Reform Code
```python
def get_option6_reform():
    """Option 6: Phased Roth-Style Swap"""
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
```

**Reform Explanation:** This complex phased reform gradually increases employer payroll tax inclusion (starting at 13.07% in 2026, reaching 100% by 2033) while simultaneously phasing down Social Security benefit taxation rates starting in 2029. The base rate decreases from current law (50%) to 45% in 2029, continuing down to 0% by 2038, while the additional rate phases from 85% down to 0% by 2045. This creates a gradual transition from taxing benefits to taxing employer contributions.
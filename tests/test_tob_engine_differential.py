"""The full-H5 worker stores the engine's taxation-of-benefits revenue as is.

These tests build small PolicyEngine US household simulations, so they run the
installed engine. The differential test holds on any engine: the worker's
stored arrays must equal what the engine's own ``tob_revenue_*`` formulas
return, signed, from an independent simulation. The witness test pins the
target release's definition (the change in chapter 1 income tax liability)
and skips until the installed engine defines ``income_tax_chapter_1``.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("policyengine_us")

from policyengine_us import Simulation  # noqa: E402

from src.reform_full_h5_output_manifest import TOB_REVENUE_VARIABLES  # noqa: E402
from src.reform_full_h5_worker import save_complete_microsimulation_h5  # noqa: E402

TOB = ("tob_revenue_oasdi", "tob_revenue_medicare_hi")
# Engines whose TOB formulas allocate by the pre-1993 inclusion keep negative
# unit differences; older engines floored each unit at zero.
SIGNED_TOB_MARKER = "tax_unit_taxable_social_security_pre_1993"
CHAPTER_1_LIABILITY = "income_tax_chapter_1"

# PolicyEngine US's own signed-allocation witness (tests/policy/baseline/gov/
# ssa/revenue/tob_revenue_oasdi.yaml): inclusion raises AGI, which releases
# more of the 60% charitable limit and shrinks the elderly credit by less, so
# income tax falls as inclusion rises. The engine expects OASDI -17.50 and
# HI -12.25 in 2024.
NEGATIVE_ALLOCATION = {
    "person": {
        "age": 67,
        "social_security": 1_000,
        "taxable_interest_income": 11_500,
        "tax_exempt_interest_income": 23_000,
        "charitable_cash_donations": 20_000,
    },
    "tax_unit": {
        "filing_status": "SINGLE",
        "tax_unit_itemizes": True,
        "itemized_medical_expenses": 0,
        "salt_deduction": 0,
    },
}


def _situation(year: int, cases: dict[str, dict]) -> dict:
    """One single-filer household per case, each in its own group entities."""
    situation = {
        entity: {}
        for entity in (
            "people",
            "tax_units",
            "households",
            "marital_units",
            "spm_units",
            "families",
        )
    }
    for name, case in cases.items():
        head = f"head_{name}"
        children = [f"child{k}_{name}" for k in range(case.get("children", 0))]
        members = [head, *children]
        situation["people"][head] = {
            variable: {year: value} for variable, value in case["person"].items()
        }
        for k, child in enumerate(children):
            situation["people"][child] = {"age": {year: 8 + k}}
        situation["tax_units"][f"tax_unit_{name}"] = {
            "members": members,
            **{
                variable: {year: value}
                for variable, value in case.get("tax_unit", {}).items()
            },
        }
        situation["households"][f"household_{name}"] = {
            "members": members,
            "state_name": {year: "TX"},
        }
        for person in members:
            situation["marital_units"][f"marital_unit_{person}"] = {"members": [person]}
        situation["spm_units"][f"spm_unit_{name}"] = {
            "members": members,
            # Childless and retired units: skip unrelated monthly TANF work.
            "takes_up_tanf_if_eligible": {year: False},
        }
        situation["families"][f"family_{name}"] = {"members": members}
    return situation


def _change_without_taxable_ss(sim, year: int, variable: str) -> np.ndarray:
    """``variable`` with full inclusion minus ``variable`` with none.

    This is the test's independent oracle. It uses the counterfactual state
    the engine's formulas use: a cloned branch with taxable Social Security
    neutralized and every computed array cleared.
    """
    full = np.asarray(sim.calculate(variable, year)).copy()
    branch_name = "witness_no_taxable_ss"
    branch = sim.get_branch(branch_name, clone_system=True)
    try:
        branch.tax_benefit_system.neutralize_variable(
            "tax_unit_taxable_social_security"
        )
        inputs = set(branch.input_variables)
        for name in list(branch.tax_benefit_system.variables):
            if name not in inputs:
                branch.delete_arrays(name)
        without = np.asarray(branch.calculate(variable, year)).copy()
    finally:
        sim.branches.pop(branch_name, None)
    return full - without


DIFFERENTIAL_YEAR = 2024
DIFFERENTIAL_CASES = {
    "tier_2": {
        "person": {
            "age": 70,
            "social_security": 30_000,
            "taxable_interest_income": 40_000,
        }
    },
    "high_income": {
        "person": {
            "age": 70,
            "social_security": 40_000,
            "taxable_interest_income": 190_000,
        }
    },
    "no_benefits": {"person": {"age": 70, "taxable_interest_income": 50_000}},
    "negative_allocation": NEGATIVE_ALLOCATION,
}


def test_worker_stores_exactly_the_engine_tob_arrays(tmp_path: Path):
    year = DIFFERENTIAL_YEAR
    situation = _situation(year, DIFFERENTIAL_CASES)

    reference = Simulation(situation=situation)
    expected = {name: np.asarray(reference.calculate(name, year)) for name in TOB}
    signed_engine = SIGNED_TOB_MARKER in reference.tax_benefit_system.variables
    del reference

    worker_sim = Simulation(situation=situation)
    output = tmp_path / "cell.h5"
    metadata = save_complete_microsimulation_h5(
        worker_sim,
        output,
        year=year,
        fail_on_empty_entity=False,
        # Other tax-unit outputs first, so the TOB formulas run on a
        # simulation that already holds cached tax arrays, as in a cell.
        variables_by_entity={
            "tax_unit": [
                "tax_unit_id",
                "income_tax",
                "tax_unit_taxable_social_security",
                *TOB,
            ]
        },
    )
    stored = pd.read_hdf(output, "tax_unit")

    assert set(TOB) == set(TOB_REVENUE_VARIABLES)
    assert metadata["tob_materialization"]["materialized"] == sorted(TOB)
    for name in TOB:
        np.testing.assert_array_equal(stored[name].to_numpy(), expected[name])
    np.testing.assert_array_equal(
        stored["tax_unit_taxable_social_security"].to_numpy()[2], 0
    )
    np.testing.assert_array_equal(
        [stored[name].to_numpy()[2] for name in TOB], [0.0, 0.0]
    )
    negative = list(DIFFERENTIAL_CASES).index("negative_allocation")
    if signed_engine:
        # The worker keeps the engine's negative allocation: no floor.
        np.testing.assert_allclose(
            [stored[name].to_numpy()[negative] for name in TOB],
            [-17.50, -12.25],
            atol=0.01,
        )
    else:
        assert all(stored[name].to_numpy()[negative] >= 0 for name in TOB)


WITNESS_CASES = {
    # A single Texas filer aged 70 with $40,000 of benefits and $190,000 of
    # interest: inclusion pushes MAGI past the $200,000 NIIT threshold, so the
    # change in total income tax carries NIIT that the chapter 1 definition
    # leaves out.
    "niit": (
        2026,
        {
            "person": {
                "age": 70,
                "social_security": 40_000,
                "taxable_interest_income": 190_000,
            }
        },
    ),
    # Inclusion pushes AGI into the EITC phase-out, so the whole difference is
    # a smaller refundable credit.
    "refundable_credit": (
        2026,
        {
            "person": {
                "age": 50,
                "social_security": 16_000,
                "employment_income": 22_000,
            },
            "children": 1,
        },
    ),
    # A negative difference must survive into both TOB variables.
    "negative_difference": (2024, NEGATIVE_ALLOCATION),
}


@pytest.fixture(scope="module")
def witness_simulations():
    by_year: dict[int, dict[str, dict]] = {}
    for name, (year, case) in WITNESS_CASES.items():
        by_year.setdefault(year, {})[name] = case
    simulations = {}
    for year, cases in by_year.items():
        sim = Simulation(situation=_situation(year, cases))
        if CHAPTER_1_LIABILITY not in sim.tax_benefit_system.variables:
            pytest.skip(
                f"installed PolicyEngine US lacks {CHAPTER_1_LIABILITY}; the "
                "chapter 1 TOB definition is not released yet"
            )
        for index, name in enumerate(cases):
            simulations[name] = (sim, year, index)
    return simulations


@pytest.mark.parametrize("case", list(WITNESS_CASES))
def test_tob_total_is_the_change_in_chapter_1_liability(witness_simulations, case):
    sim, year, index = witness_simulations[case]
    total = sum(np.asarray(sim.calculate(name, year)) for name in TOB)
    chapter_1_change = _change_without_taxable_ss(sim, year, CHAPTER_1_LIABILITY)

    np.testing.assert_allclose(total[index], chapter_1_change[index], atol=0.01)
    if case == "niit":
        niit_change = _change_without_taxable_ss(sim, year, "net_investment_income_tax")
        assert niit_change[index] > 0
    if case == "refundable_credit":
        eitc_change = _change_without_taxable_ss(sim, year, "eitc")
        assert eitc_change[index] < 0
    if case == "negative_difference":
        assert total[index] < 0
        assert all(np.asarray(sim.calculate(name, year))[index] < 0 for name in TOB)

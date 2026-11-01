"""Gross-income coverage and the independent income calibration guards."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from src import pipeline

DISTRIBUTION_INPUTS = (
    "taxable_sep_distributions",
    "taxable_401k_distributions",
    "taxable_403b_distributions",
    "keogh_distributions",
)


@pytest.mark.parametrize("name", DISTRIBUTION_INPUTS)
def test_retirement_distribution_sources_are_scaled_and_capped(name):
    assert name in pipeline.OTHER_INCOME_SCALE_CANDIDATES
    assert name in pipeline.GROWTH_CAP_VARIABLES


def _formula(person, period, parameters):
    return person("formula_income", period) * person("divorce_year", period)


def _old_formula(person, period, parameters):
    return person("obsolete_income", period)


def _named_inputs_formula(person, period, parameters):
    names = ["formula_income", "taxable_401k_distributions"]
    return sum(person(name, period) for name in names)


def _unemployment_formula(person, period, parameters):
    return person("weeks_unemployed", period)


def _source_sim(variables, sources):
    return SimpleNamespace(
        tax_benefit_system=SimpleNamespace(
            variables=variables,
            parameters=SimpleNamespace(
                get_child=lambda name: lambda instant: sources,
            ),
        )
    )


def _input(**kwargs):
    return SimpleNamespace(formulas={}, adds=None, **kwargs)


def test_completeness_follows_adds_and_active_named_formula_inputs():
    variables = {
        name: _input()
        for name in [
            "taxable_401k_distributions",
            "formula_income",
            "divorce_year",
            "obsolete_income",
            "unrelated_income",
        ]
    }
    variables["root"] = SimpleNamespace(adds=["aggregate", "computed"], formulas={})
    variables["aggregate"] = SimpleNamespace(
        adds="gov.irs.gross_income.nested_sources", formulas={}
    )
    variables["computed"] = SimpleNamespace(
        adds=None,
        formulas={"2020-01-01": _old_formula, "2024-01-01": _formula},
    )
    sources = {
        "gov.irs.gross_income.sources": ["root"],
        "gov.irs.gross_income.nested_sources": ["taxable_401k_distributions"],
    }
    sim = _source_sim(variables, [])
    sim.tax_benefit_system.parameters.get_child = lambda name: (
        lambda instant: sources[name]
    )
    frame = pd.DataFrame(
        {
            f"{name}__2050": [1.0]
            for name in variables
            if name
            not in {
                "root",
                "aggregate",
                "computed",
            }
        }
    )

    assert pipeline.gross_income_stored_inputs(frame, sim, 2050) == {
        "taxable_401k_distributions",
        "formula_income",
        "divorce_year",
    }
    with pytest.raises(ValueError, match="formula_income") as error:
        pipeline.assert_gross_income_sources_classified(frame, sim, 2050)
    assert "obsolete_income" not in str(error.value)
    assert "unrelated_income" not in str(error.value)


def test_completeness_names_every_unclassified_stored_source():
    names = ["new_income_a", "new_income_b", "salt_refund_income"]
    sim = _source_sim({name: _input() for name in names}, names)
    frame = pd.DataFrame({f"{name}__2030": [0.0] for name in names})
    with pytest.raises(ValueError) as error:
        pipeline.assert_gross_income_sources_classified(frame, sim, 2030)
    assert "new_income_a" in str(error.value)
    assert "new_income_b" in str(error.value)
    assert "salt_refund_income" not in str(error.value)


def test_completeness_follows_named_formula_input_lists():
    variables = {
        "root": SimpleNamespace(
            adds=None, formulas={"2024-01-01": _named_inputs_formula}
        ),
        "formula_income": _input(),
        "taxable_401k_distributions": _input(),
    }
    frame = pd.DataFrame(
        {
            "formula_income__2050": [1.0],
            "taxable_401k_distributions__2050": [2.0],
        }
    )
    sim = _source_sim(variables, ["root"])
    assert pipeline.gross_income_stored_inputs(frame, sim, 2050) == {
        "formula_income",
        "taxable_401k_distributions",
    }


def test_completeness_ignores_parameter_amounts_in_adds():
    variables = {
        "root": SimpleNamespace(
            adds=["gov.amount", "taxable_401k_distributions"], formulas={}
        ),
        "taxable_401k_distributions": _input(),
    }
    sim = _source_sim(variables, ["root"])
    sim.tax_benefit_system.parameters.get_child = lambda name: (
        lambda instant: ["root"] if name == "gov.irs.gross_income.sources" else 100.0
    )
    frame = pd.DataFrame({"taxable_401k_distributions__2050": [5.0]})
    pipeline.assert_gross_income_sources_classified(frame, sim, 2050)


def test_completeness_stops_at_stored_formula_override_and_handles_cycles():
    variables = {
        "root": SimpleNamespace(adds=["cycle", "salt_refund_income"], formulas={}),
        "cycle": SimpleNamespace(adds=["root"], formulas={}),
        "salt_refund_income": SimpleNamespace(adds=["hidden_income"], formulas={}),
        "hidden_income": _input(),
    }
    sim = _source_sim(variables, ["root"])
    frame = pd.DataFrame({"salt_refund_income__2050": [5.0]})
    assert pipeline.gross_income_stored_inputs(frame, sim, 2050) == {
        "salt_refund_income"
    }
    pipeline.assert_gross_income_sources_classified(frame, sim, 2050)


def test_unscaled_source_exceptions_have_individual_reasons():
    expected = {
        "salt_refund_income",
        "alimony_income",
        "unemployment_compensation",
        "disability_benefits",
    }
    assert expected <= pipeline.UNSCALED_GROSS_INCOME_SOURCES.keys()
    reasons = [pipeline.UNSCALED_GROSS_INCOME_SOURCES[name] for name in expected]
    assert all(reason.strip() for reason in reasons)
    assert len(set(reasons)) >= 3


def test_gross_income_dependency_controls_are_explicitly_unscaled():
    names = {
        "age",
        "is_full_time_college_student",
        "is_related_to_head_or_spouse",
        "is_separated",
        "is_surviving_spouse",
        "tax_unit_role_input",
        "traditional_401k_contributions_desired",
        "roth_401k_contributions_desired",
        "weeks_unemployed",
    }
    assert names <= pipeline.UNSCALED_GROSS_INCOME_SOURCES.keys()
    sim = _source_sim({name: _input() for name in names}, names)
    frame = pd.DataFrame({f"{name}__2050": [1.0] for name in names})
    pipeline.assert_gross_income_sources_classified(frame, sim, 2050)


def test_computed_unemployment_classifies_its_stored_duration_input():
    variables = {
        "unemployment_compensation": SimpleNamespace(
            adds=None, formulas={"2024-01-01": _unemployment_formula}
        ),
        "weeks_unemployed": _input(),
    }
    sim = _source_sim(variables, ["unemployment_compensation"])
    frame = pd.DataFrame({"weeks_unemployed__2030": [26]})
    assert pipeline.gross_income_stored_inputs(frame, sim, 2030) == {"weeks_unemployed"}
    pipeline.assert_gross_income_sources_classified(frame, sim, 2030)


def test_build_checks_source_coverage_before_scaling(monkeypatch, tmp_path):
    from tests import pipeline_fakes as fakes

    year = 2030
    frame = fakes.make_frame(year)
    frame[f"new_income__{year}"] = 100.0
    engine = fakes.FakeEngine(year, frame, {})
    fakes.install(monkeypatch, engine)
    original = fakes.FakeParameters.get_child

    def get_child(parameters, name):
        if name == "gov.irs.gross_income.sources":
            return lambda instant: ["new_income"]
        return original(parameters, name)

    monkeypatch.setattr(fakes.FakeParameters, "get_child", get_child)
    with pytest.raises(ValueError, match="new_income"):
        pipeline.build_year(year, "fake-base", tmp_path)
    assert not (tmp_path / f"{year}.h5").exists()


def test_completeness_property_for_unknown_stored_sources():
    hypothesis = pytest.importorskip("hypothesis")
    st = pytest.importorskip("hypothesis.strategies")

    @hypothesis.given(st.sets(st.integers(min_value=0, max_value=20), min_size=1))
    @hypothesis.settings(max_examples=30, deadline=None)
    def check(indices):
        names = {f"new_income_{index}" for index in indices}
        sim = _source_sim({name: _input() for name in names}, names)
        frame = pd.DataFrame({f"{name}__2050": [0.0] for name in names})
        with pytest.raises(ValueError) as error:
            pipeline.assert_gross_income_sources_classified(frame, sim, 2050)
        assert all(name in str(error.value) for name in names)

    check()


def test_guard_does_not_double_count_dividend_and_schedule_j_memos():
    components = {
        name for names in pipeline.INCOME_GUARD_GROUPS.values() for name in names
    }
    values = {
        "non_qualified_dividend_income": np.array([10_000.0, 10_000.0, 0.0]),
        "qualified_bdc_income": np.array([6_000.0, 0.0, 0.0]),
        "qualified_reit_and_ptp_income": np.array([3_000.0, 0.0, 0.0]),
        "farm_income": np.array([1_000.0, 0.0, 0.0]),
    }
    sim = SimpleNamespace(
        tax_benefit_system=SimpleNamespace(
            variables={name: _input() for name in components}
        ),
        calculate=lambda name, **kwargs: SimpleNamespace(
            values=values.get(name, np.zeros(3))
        ),
    )
    guard = pipeline._income_guard_vectors(sim, 2050)[
        "income_guard_ordinary_nonpayroll_income"
    ]
    gross = values["non_qualified_dividend_income"]
    np.testing.assert_array_equal(guard, gross)
    initial_weights = np.array([1.0, 1.0, 1.0])
    tilted_weights = np.array([0.5, 2.0, 0.5])
    assert guard @ tilted_weights - guard @ initial_weights == 5_000.0


def test_guard_totals_equal_the_unique_sources_they_name():
    groups = pipeline.INCOME_GUARD_GROUPS
    all_leaves = [
        leaf
        for names in groups.values()
        for name in names
        for leaf in pipeline.PRE_2X_NAME_LEAVES.get(name, (name,))
    ]
    assert len(all_leaves) == len(set(all_leaves))
    assert "partnership_s_corp_income" in groups["ordinary_nonpayroll_income"]
    assert {"partnership_income", "s_corp_income"} <= set(all_leaves)
    assert not {
        "qualified_bdc_income",
        "qualified_reit_and_ptp_income",
        "farm_income",
    } & set(all_leaves)
    values = {
        name: np.array([index + 1.0, (index + 1.0) * 2])
        for index, name in enumerate(sorted(all_leaves))
    }
    values["partnership_s_corp_income"] = (
        values["partnership_income"] + values["s_corp_income"]
    )
    sim = SimpleNamespace(
        tax_benefit_system=SimpleNamespace(
            variables={name: _input() for name in values}
        ),
        calculate=lambda name, **kwargs: SimpleNamespace(values=values[name]),
    )
    actual = pipeline._income_guard_vectors(sim, 2050)
    weights = np.array([3.0, 5.0])
    for group, names in groups.items():
        leaves = {
            leaf
            for name in names
            for leaf in pipeline.PRE_2X_NAME_LEAVES.get(name, (name,))
        }
        expected = sum(values[leaf] for leaf in leaves)
        np.testing.assert_array_equal(actual[f"income_guard_{group}"], expected)
        assert weights @ actual[f"income_guard_{group}"] == weights @ expected


@pytest.mark.parametrize("year,seed", [(2030, 40), (2050, 7)])
def test_fake_build_targets_leave_room_for_benefit_tax_calibration(
    monkeypatch, tmp_path, year, seed
):
    from tests import pipeline_fakes as fakes

    frame = fakes.make_frame(year, seed=seed)
    rates = {
        f"calibration.fake.{name}": 0.02
        for name in fakes.frame_variable_names() + list(pipeline.KNOWN_ABSENT_INPUTS)
    }
    rates["calibration.fake.qualified_dividend_income"] = 0.09
    engine = fakes.FakeEngine(year, frame, rates)
    fakes.install(monkeypatch, engine)
    targets = pipeline.load_tob_targets(year)
    ss_target = pipeline.load_economic_targets(year)["ss_total"]
    # The fake taxes at 12% plus 5%, on at most 85% of benefits. A target
    # exceeding this bound cannot coexist with its fixed benefit target.
    assert sum(targets.values()) < 0.17 * 0.85 * ss_target
    economic = fakes.FakeEconomicReform if year == 2050 else None
    sentinel = pipeline.build_year(
        year, "fake-base", tmp_path, economic_assumption_reform=economic
    )
    assert np.isfinite(sentinel["max_constraint_pct_error"])
    assert sentinel["max_constraint_pct_error"] <= 1e-4
    for name, target in targets.items():
        assert sentinel[f"{name}_achieved"] == pytest.approx(target, rel=1e-4)

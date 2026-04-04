from __future__ import annotations

import numpy as np

from src.year_runner import (
    BaselineResult,
    ScenarioAggregate,
    ScenarioHouseholdMetrics,
    aggregate_scenario_household_metrics,
    align_weights_to_households,
    build_reform_result_from_aggregates,
)


def test_align_weights_to_households_reindexes_by_household_id() -> None:
    aligned = align_weights_to_households(
        household_ids=np.array([30, 10, 20]),
        weight_household_ids=np.array([10, 20, 30]),
        household_weights=np.array([1.5, 2.5, 3.5]),
    )

    assert np.array_equal(aligned, np.array([3.5, 1.5, 2.5]))


def test_aggregate_scenario_household_metrics_uses_explicit_weights() -> None:
    metrics = ScenarioHouseholdMetrics(
        household_ids=np.array([2, 1]),
        income_tax=np.array([10.0, 20.0]),
        tob_medicare_hi=np.array([1.0, 2.0]),
        tob_oasdi=np.array([3.0, 4.0]),
        employer_ss_tax_revenue=np.array([5.0, 6.0]),
        employer_medicare_tax_revenue=np.array([7.0, 8.0]),
    )

    aggregate = aggregate_scenario_household_metrics(
        metrics,
        weight_household_ids=np.array([1, 2]),
        household_weights=np.array([100.0, 10.0]),
    )

    assert aggregate.revenue == 2100.0
    assert aggregate.tob_medicare_hi == 210.0
    assert aggregate.tob_oasdi == 430.0
    assert aggregate.tob_total == 640.0
    assert aggregate.employer_ss_tax_revenue == 650.0
    assert aggregate.employer_medicare_tax_revenue == 870.0


def test_build_reform_result_from_aggregates_uses_totals_only() -> None:
    baseline = BaselineResult(
        revenue=1_000.0,
        tob_medicare_hi=300.0,
        tob_oasdi=700.0,
        tob_total=1_000.0,
    )
    reform = ScenarioAggregate(
        revenue=1_250.0,
        tob_medicare_hi=250.0,
        tob_oasdi=500.0,
        tob_total=750.0,
        employer_ss_tax_revenue=600.0,
        employer_medicare_tax_revenue=200.0,
    )

    result = build_reform_result_from_aggregates(
        reform_id="option5",
        year=2040,
        baseline=baseline,
        reform_totals=reform,
        employer_net_reforms={"option5", "option6", "option12"},
        default_net_impact_mode="direct",
    )

    assert result["revenue_impact"] == 250.0
    assert result["tob_oasdi_impact"] == -200.0
    assert result["tob_medicare_hi_impact"] == -50.0
    assert result["employer_ss_tax_revenue"] == 600.0
    assert result["employer_medicare_tax_revenue"] == 200.0
    assert result["oasdi_gain"] == 600.0
    assert result["hi_gain"] == 200.0
    assert result["oasdi_loss"] == 200.0
    assert result["hi_loss"] == 50.0
    assert result["oasdi_net_impact"] == 400.0
    assert result["hi_net_impact"] == 150.0

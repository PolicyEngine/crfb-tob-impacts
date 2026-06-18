from pathlib import Path

import h5py
import json
import numpy as np
import pandas as pd
import pytest
from policyengine_core.periods import period
from policyengine_core.periods.config import ETERNITY

from src.year_runner import (
    BaselineResult,
    ScenarioAggregate,
    ScenarioHouseholdMetrics,
    build_baseline_reconciliation_report,
    compute_reform_result,
    create_household_sampled_dataset,
    load_baseline,
    load_baseline_from_metrics,
    load_scenario_household_metrics,
    save_microsimulation_raw_h5,
    save_scenario_household_metrics,
    scenario_aggregate_from_dict,
    scenario_aggregate_to_dict,
    validate_baseline_reconciliation,
)


def _write_metrics(path: Path) -> None:
    np.savez(
        path,
        household_ids=np.array([2, 1]),
        income_tax=np.array([20.0, 10.0]),
        tob_medicare_hi=np.array([2.0, 1.0]),
        tob_oasdi=np.array([4.0, 3.0]),
        social_security=np.array([200.0, 100.0]),
        taxable_payroll=np.array([500.0, 400.0]),
        employer_ss_tax_revenue=np.array([6.0, 5.0]),
        employer_medicare_tax_revenue=np.array([8.0, 7.0]),
    )


def test_load_scenario_household_metrics_round_trips_npz(tmp_path: Path):
    metrics_path = tmp_path / "metrics.npz"
    _write_metrics(metrics_path)

    metrics = load_scenario_household_metrics(metrics_path)

    np.testing.assert_array_equal(metrics.household_ids, np.array([2, 1]))
    np.testing.assert_array_equal(metrics.income_tax, np.array([20.0, 10.0]))
    np.testing.assert_array_equal(metrics.tob_oasdi, np.array([4.0, 3.0]))
    np.testing.assert_array_equal(metrics.social_security, np.array([200.0, 100.0]))
    np.testing.assert_array_equal(metrics.taxable_payroll, np.array([500.0, 400.0]))


def test_save_scenario_household_metrics_round_trips_npz(tmp_path: Path):
    metrics_path = tmp_path / "scenario" / "metrics.npz"
    metrics = _single_household_metrics(revenue=42.0)

    save_scenario_household_metrics(metrics, metrics_path)

    loaded = load_scenario_household_metrics(metrics_path)
    np.testing.assert_array_equal(loaded.household_ids, np.array([1]))
    np.testing.assert_array_equal(loaded.income_tax, np.array([42.0]))
    np.testing.assert_array_equal(loaded.tob_medicare_hi, np.array([1.0]))
    np.testing.assert_array_equal(loaded.tob_oasdi, np.array([2.0]))
    np.testing.assert_array_equal(loaded.household_weight, np.array([1.0]))


def test_save_microsimulation_raw_h5_writes_entity_tables(tmp_path: Path):
    year_period = period("2040")
    other_period = period("2041")
    eternity_period = period(ETERNITY)
    simulation = _FakeSimulation(
        {
            "person_id": _FakeHolder({("default", eternity_period): np.array([1, 2])}),
            "person_household_id": _FakeHolder(
                {("default", eternity_period): np.array([1, 1])}
            ),
            "household_id": _FakeHolder({("default", eternity_period): np.array([1])}),
            "household_weight": _FakeHolder(
                {("default", year_period): np.array([100.0])}
            ),
            "income_tax": _FakeHolder({("default", year_period): np.array([250.0])}),
            "wrong_period": _FakeHolder({("default", other_period): np.array([999.0])}),
        }
    )
    output_path = tmp_path / "raw" / "scenario.h5"

    metadata = save_microsimulation_raw_h5(
        simulation,
        output_path,
        year=2040,
    )

    assert metadata["artifact_type"] == ("policyengine_us_entity_table_raw_scenario_h5")
    assert metadata["variable_count"] == 5
    with pd.HDFStore(output_path, mode="r") as store:
        person = store["person"]
        household = store["household"]
        tax_unit = store["tax_unit"]
    assert list(person.columns) == ["person_household_id", "person_id"]
    assert list(household.columns) == ["household_id", "household_weight"]
    assert list(tax_unit.columns) == ["income_tax"]
    assert "wrong_period" not in household.columns
    np.testing.assert_array_equal(tax_unit["income_tax"].to_numpy(), np.array([250.0]))


def test_scenario_aggregate_json_round_trip():
    aggregate = ScenarioAggregate(
        revenue=1,
        tob_medicare_hi=2,
        tob_oasdi=3,
        tob_total=5,
        social_security=6,
        taxable_payroll=7,
        employer_ss_tax_revenue=8,
        employer_medicare_tax_revenue=9,
    )

    loaded = scenario_aggregate_from_dict(scenario_aggregate_to_dict(aggregate))

    assert loaded == aggregate


def test_load_baseline_from_metrics_rejects_raw_weight_reaggregation(tmp_path: Path):
    metrics_path = tmp_path / "metrics.npz"
    _write_metrics(metrics_path)

    with pytest.raises(RuntimeError, match="MicroSeries.sum"):
        load_baseline_from_metrics(metrics_path)


def _write_reconciliation_metadata(
    dataset_path: Path,
    *,
    ss_total: float = 12_000.0,
    payroll_total: float = 45_000.0,
    oasdi_tob: float = 340.0,
    hi_tob: float = 120.0,
) -> None:
    metadata = {
        "calibration_audit": {
            "constraints": {
                "ss_total": {"target": ss_total, "achieved": ss_total},
                "payroll_total": {
                    "target": payroll_total,
                    "achieved": payroll_total,
                },
                "oasdi_tob": {"target": oasdi_tob, "achieved": oasdi_tob},
                "hi_tob": {"target": hi_tob, "achieved": hi_tob},
            }
        }
    }
    Path(f"{dataset_path}.metadata.json").write_text(
        json.dumps(metadata),
        encoding="utf-8",
    )


def _write_tax_assumption_metadata(dataset_path: Path) -> None:
    metadata = {
        "year": 2035,
        "tax_assumption": {
            "name": "trustees-2025-core-thresholds-v1",
            "start_year": 2035,
            "end_year": 2100,
        },
        "calibration_audit": {"constraints": {}},
    }
    Path(f"{dataset_path}.metadata.json").write_text(
        json.dumps(metadata),
        encoding="utf-8",
    )


def _single_household_metrics(revenue: float = 10.0) -> ScenarioHouseholdMetrics:
    return ScenarioHouseholdMetrics(
        household_ids=np.array([1]),
        income_tax=np.array([revenue]),
        tob_medicare_hi=np.array([1.0]),
        tob_oasdi=np.array([2.0]),
        social_security=np.array([100.0]),
        taxable_payroll=np.array([200.0]),
        employer_ss_tax_revenue=np.array([3.0]),
        employer_medicare_tax_revenue=np.array([4.0]),
        household_weight=np.array([1.0]),
    )


def _single_household_aggregate(revenue: float = 10.0) -> ScenarioAggregate:
    return ScenarioAggregate(
        revenue=revenue,
        tob_medicare_hi=1.0,
        tob_oasdi=2.0,
        tob_total=3.0,
        social_security=100.0,
        taxable_payroll=200.0,
        employer_ss_tax_revenue=3.0,
        employer_medicare_tax_revenue=4.0,
    )


class _FakeEntity:
    def __init__(self, key: str):
        self.key = key


class _FakeVariable:
    def __init__(self, entity_key: str):
        self.entity = _FakeEntity(entity_key)


class _FakePopulation:
    def __init__(self, entity_key: str, count: int):
        self.entity = _FakeEntity(entity_key)
        self.count = count


class _FakeHolder:
    def __init__(self, arrays):
        self.arrays = arrays

    def get_known_branch_periods(self):
        return list(self.arrays)

    def get_array(self, known_period, branch_name="default"):
        return self.arrays[(branch_name, known_period)]


class _FakeTaxBenefitSystem:
    def __init__(self, variable_entities: dict[str, str]):
        self.variables = {
            name: _FakeVariable(entity_key)
            for name, entity_key in variable_entities.items()
        }


class _FakeSimulation:
    def __init__(self, holders: dict[str, _FakeHolder]):
        variable_entities = {
            "person_id": "person",
            "person_household_id": "person",
            "household_id": "household",
            "household_weight": "household",
            "income_tax": "tax_unit",
            "wrong_period": "household",
        }
        self.tax_benefit_system = _FakeTaxBenefitSystem(variable_entities)
        self.holders = holders
        self.populations = {
            "person": _FakePopulation("person", 2),
            "household": _FakePopulation("household", 1),
            "tax_unit": _FakePopulation("tax_unit", 1),
        }

    def get_holder(self, variable_name: str):
        return self.holders[variable_name]


def test__given_active_tax_assumption_metadata__then_load_baseline_applies_matching_reform(
    monkeypatch,
    tmp_path: Path,
):
    dataset_path = tmp_path / "2035.h5"
    dataset_path.write_text("", encoding="utf-8")
    _write_tax_assumption_metadata(dataset_path)
    baseline_reform = object()

    monkeypatch.setattr(
        "src.year_runner.load_tax_assumption_reform_for_dataset",
        lambda dataset_name, year: baseline_reform,
    )

    def compute_metrics_and_aggregate(*, year, dataset_name, reform, progress_label):
        assert year == 2035
        assert Path(dataset_name) == dataset_path
        assert reform is baseline_reform
        return _single_household_metrics(), _single_household_aggregate()

    monkeypatch.setattr(
        "src.year_runner.compute_scenario_household_metrics_and_aggregate",
        compute_metrics_and_aggregate,
    )

    baseline = load_baseline(2035, dataset_path)

    assert baseline.tax_assumption_name == "trustees-2025-core-thresholds-v1"
    assert baseline.tax_assumption_active is True


def test__given_active_tax_assumption_metadata__then_explicit_baseline_reform_is_ignored(
    monkeypatch,
    tmp_path: Path,
):
    dataset_path = tmp_path / "2035.h5"
    dataset_path.write_text("", encoding="utf-8")
    _write_tax_assumption_metadata(dataset_path)
    metadata_reform = object()
    explicit_reform = object()

    monkeypatch.setattr(
        "src.year_runner.load_tax_assumption_reform_for_dataset",
        lambda dataset_name, year: metadata_reform,
    )

    def compute_metrics_and_aggregate(*, year, dataset_name, reform, progress_label):
        assert reform is metadata_reform
        return _single_household_metrics(), _single_household_aggregate()

    monkeypatch.setattr(
        "src.year_runner.compute_scenario_household_metrics_and_aggregate",
        compute_metrics_and_aggregate,
    )

    baseline = load_baseline(
        2035,
        dataset_path,
        baseline_reform=explicit_reform,
    )

    assert baseline.tax_assumption_name == "trustees-2025-core-thresholds-v1"
    assert baseline.tax_assumption_active is True


def test__given_malformed_tax_assumption_metadata__then_load_baseline_fails_closed(
    tmp_path: Path,
):
    dataset_path = tmp_path / "2035.h5"
    dataset_path.write_text("", encoding="utf-8")
    Path(f"{dataset_path}.metadata.json").write_text("{", encoding="utf-8")

    with pytest.raises(json.JSONDecodeError):
        load_baseline(2035, dataset_path)


def test__given_active_tax_assumption_metadata__then_reform_scoring_rejects_untagged_baseline(
    monkeypatch,
    tmp_path: Path,
):
    dataset_path = tmp_path / "2035.h5"
    dataset_path.write_text("", encoding="utf-8")
    _write_tax_assumption_metadata(dataset_path)
    monkeypatch.setattr(
        "src.year_runner.load_tax_assumption_reform_for_dataset",
        lambda dataset_name, year: object(),
    )
    baseline = BaselineResult(
        revenue=0.0,
        tob_medicare_hi=0.0,
        tob_oasdi=0.0,
        tob_total=0.0,
        social_security=0.0,
        taxable_payroll=0.0,
    )

    with pytest.raises(ValueError, match="tax assumption does not match"):
        compute_reform_result(
            reform_id="option1",
            year=2035,
            scoring_type="static",
            dataset_name=dataset_path,
            baseline=baseline,
            reform_functions={},
            behavioral_functions={},
            employer_net_reforms=frozenset(),
        )


def test__given_tagged_tax_assumption_baseline__then_reform_scoring_stacks_baseline_reform(
    monkeypatch,
    tmp_path: Path,
):
    dataset_path = tmp_path / "2035.h5"
    dataset_path.write_text("", encoding="utf-8")
    _write_tax_assumption_metadata(dataset_path)
    baseline_reform = object()
    policy_reform = object()

    monkeypatch.setattr(
        "src.year_runner.load_tax_assumption_reform_for_dataset",
        lambda dataset_name, year: baseline_reform,
    )

    def compute_metrics_and_aggregate(*, year, dataset_name, reform, progress_label):
        assert reform == (baseline_reform, policy_reform)
        return (
            _single_household_metrics(revenue=20.0),
            _single_household_aggregate(revenue=20.0),
        )

    monkeypatch.setattr(
        "src.year_runner.compute_scenario_household_metrics_and_aggregate",
        compute_metrics_and_aggregate,
    )
    baseline = BaselineResult(
        revenue=10.0,
        tob_medicare_hi=1.0,
        tob_oasdi=2.0,
        tob_total=3.0,
        social_security=100.0,
        taxable_payroll=200.0,
        tax_assumption_name="trustees-2025-core-thresholds-v1",
        tax_assumption_active=True,
    )

    result = compute_reform_result(
        reform_id="option1",
        year=2035,
        scoring_type="static",
        dataset_name=dataset_path,
        baseline=baseline,
        reform_functions={"option1": lambda: policy_reform},
        behavioral_functions={},
        employer_net_reforms=frozenset(),
    )

    assert result["baseline_tax_assumption_name"] == (
        "trustees-2025-core-thresholds-v1"
    )
    assert result["baseline_tax_assumption_active"] is True


def test_compute_reform_result_saves_requested_household_metrics(
    monkeypatch,
    tmp_path: Path,
):
    dataset_path = tmp_path / "2040.h5"
    dataset_path.write_text("", encoding="utf-8")
    Path(f"{dataset_path}.metadata.json").write_text(
        json.dumps(
            {
                "year": 2040,
                "tax_assumption": {
                    "name": "trustees-2025-core-thresholds-v1",
                    "start_year": 2035,
                    "end_year": 2100,
                },
            }
        ),
        encoding="utf-8",
    )
    metrics_path = tmp_path / "artifacts" / "option1" / "metrics.npz"
    policy_reform = object()

    monkeypatch.setattr(
        "src.year_runner.load_tax_assumption_reform_for_dataset",
        lambda dataset_name, year: None,
    )

    def compute_metrics_and_aggregate(*, year, dataset_name, reform, progress_label):
        assert year == 2040
        assert Path(dataset_name) == dataset_path
        assert reform is policy_reform
        return (
            _single_household_metrics(revenue=25.0),
            _single_household_aggregate(revenue=25.0),
        )

    monkeypatch.setattr(
        "src.year_runner.compute_scenario_household_metrics_and_aggregate",
        compute_metrics_and_aggregate,
    )
    baseline = BaselineResult(
        revenue=10.0,
        tob_medicare_hi=1.0,
        tob_oasdi=2.0,
        tob_total=3.0,
        social_security=100.0,
        taxable_payroll=200.0,
        tax_assumption_name="trustees-2025-core-thresholds-v1",
        tax_assumption_active=True,
    )

    result = compute_reform_result(
        reform_id="option1",
        year=2040,
        scoring_type="static",
        dataset_name=dataset_path,
        baseline=baseline,
        reform_functions={"option1": lambda: policy_reform},
        behavioral_functions={},
        employer_net_reforms=frozenset(),
        metrics_output_path=metrics_path,
        baseline_metrics=_single_household_metrics(revenue=10.0),
    )

    assert result["reform_household_metrics_artifact_type"] == (
        "compact_reform_household_metric_changes"
    )
    assert result["reform_household_metrics_changed_variables"] == "income_tax"
    with np.load(metrics_path) as arrays:
        assert "household_ids" in arrays.files
        assert "baseline_income_tax" in arrays.files
        assert "reform_income_tax" in arrays.files
        assert "income_tax_change" in arrays.files
        assert "household_weight" in arrays.files
        assert "baseline_tob_oasdi" not in arrays.files
        np.testing.assert_array_equal(arrays["household_ids"], np.array([1]))
        np.testing.assert_array_equal(arrays["household_weight"], np.array([1.0]))
        np.testing.assert_array_equal(arrays["baseline_income_tax"], np.array([10.0]))
        np.testing.assert_array_equal(arrays["reform_income_tax"], np.array([25.0]))
        np.testing.assert_array_equal(arrays["income_tax_change"], np.array([15.0]))
        np.testing.assert_array_equal(
            arrays["changed_metric_variables"],
            np.array(["income_tax"]),
        )


def test_baseline_reconciliation_report_compares_scored_to_calibrated_targets(
    tmp_path: Path,
):
    dataset_path = tmp_path / "2075.h5"
    dataset_path.write_text("", encoding="utf-8")
    _write_reconciliation_metadata(dataset_path)
    baseline = BaselineResult(
        revenue=1_200.0,
        tob_medicare_hi=120.0,
        tob_oasdi=340.0,
        tob_total=460.0,
        social_security=12_000.0,
        taxable_payroll=45_000.0,
    )

    report = build_baseline_reconciliation_report(dataset_path, baseline)

    assert report["baseline_reconciliation_checked"] is True
    assert report["baseline_reconciliation_max_pct_error"] == pytest.approx(0.0)


def test_baseline_reconciliation_rejects_stale_scored_artifact(tmp_path: Path):
    dataset_path = tmp_path / "2075.h5"
    dataset_path.write_text("", encoding="utf-8")
    _write_reconciliation_metadata(dataset_path, payroll_total=90_000.0)
    baseline = BaselineResult(
        revenue=1_200.0,
        tob_medicare_hi=120.0,
        tob_oasdi=340.0,
        tob_total=460.0,
        social_security=12_000.0,
        taxable_payroll=45_000.0,
    )

    with pytest.raises(ValueError, match="payroll_total"):
        validate_baseline_reconciliation(
            dataset_path,
            baseline,
            max_roundtrip_pct_error=1.0,
        )


def _write_microdata(path: Path) -> None:
    with h5py.File(path, "w") as file:
        arrays = {
            "household_id": {"2027": np.array([10, 20, 30, 40], dtype=np.int32)},
            "household_weight": {
                "2027": np.array([1.0, 0.0, 3.0, 4.0], dtype=np.float32)
            },
            "state_fips": {"2027": np.array([1, 1, 1, 1], dtype=np.int32)},
            "person_id": {"2027": np.arange(6, dtype=np.int32)},
            "person_household_id": {
                "2027": np.array([10, 10, 20, 30, 40, 40], dtype=np.int32)
            },
            "person_tax_unit_id": {
                "2027": np.array([101, 101, 201, 301, 401, 401], dtype=np.int32)
            },
            "person_spm_unit_id": {
                "2027": np.array([1001, 1001, 2001, 3001, 4001, 4001], dtype=np.int32)
            },
            "person_family_id": {
                "2027": np.array([11, 11, 21, 31, 41, 41], dtype=np.int32)
            },
            "person_marital_unit_id": {
                "2027": np.array([12, 12, 22, 32, 42, 42], dtype=np.int32)
            },
            "social_security_retirement": {
                "2027": np.array([100, 0, 100, 100, 100, 0], dtype=np.float32)
            },
            "tax_unit_id": {"2027": np.array([101, 201, 301, 401], dtype=np.int32)},
            "tax_unit_value": {
                "2025": np.array([1, 2, 3, 4], dtype=np.float32),
                "2027": np.array([5, 6, 7, 8], dtype=np.float32),
            },
            "spm_unit_id": {"2027": np.array([1001, 2001, 3001, 4001], dtype=np.int32)},
            "spm_value": {"2027": np.array([9, 10, 11, 12], dtype=np.float32)},
            "family_id": {"2027": np.array([11, 21, 31, 41], dtype=np.float32)},
            "marital_unit_id": {"2027": np.array([12, 22, 32, 42], dtype=np.int32)},
        }
        for variable_name, periods in arrays.items():
            group = file.create_group(variable_name)
            for period, values in periods.items():
                group.create_dataset(period, data=values)


def test_create_household_sampled_dataset_drops_zero_weight_households(tmp_path: Path):
    source_path = tmp_path / "2027.h5"
    _write_microdata(source_path)

    result = create_household_sampled_dataset(
        source_path,
        year=2027,
        sample_fraction=1,
        seed=0,
        drop_zero_weight_households=True,
        output_dir=tmp_path / "samples",
    )

    with h5py.File(result.dataset_name, "r") as sampled:
        np.testing.assert_array_equal(
            sampled["household_id"]["2027"][:],
            np.array([10, 30, 40], dtype=np.int32),
        )
        np.testing.assert_array_equal(
            sampled["person_household_id"]["2027"][:],
            np.array([10, 10, 30, 40, 40], dtype=np.int32),
        )
        np.testing.assert_array_equal(
            sampled["tax_unit_id"]["2027"][:],
            np.array([101, 301, 401], dtype=np.int32),
        )
        np.testing.assert_array_equal(
            sampled["tax_unit_value"]["2025"][:],
            np.array([1, 3, 4], dtype=np.float32),
        )
        np.testing.assert_array_equal(
            sampled["household_weight"]["2027"][:],
            np.array([1, 3, 4], dtype=np.float32),
        )

    assert result.metadata["microdata_households_full"] == 4
    assert result.metadata["microdata_households_sampled"] == 3
    assert result.metadata["microdata_zero_weight_households_dropped"] == 1


def test_create_household_sampled_dataset_reweights_by_selection_probability(
    tmp_path: Path,
):
    source_path = tmp_path / "2027.h5"
    _write_microdata(source_path)

    result = create_household_sampled_dataset(
        source_path,
        year=2027,
        sample_fraction=0.5,
        seed=0,
        drop_zero_weight_households=False,
        output_dir=tmp_path / "samples",
    )

    original_weights = {10: 1.0, 20: 0.0, 30: 3.0, 40: 4.0}
    with h5py.File(result.dataset_name, "r") as sampled:
        sampled_ids = sampled["household_id"]["2027"][:]
        sampled_weights = sampled["household_weight"]["2027"][:]

    assert len(sampled_ids) == 2
    assert result.metadata["microdata_certainty_households"] == 1
    for household_id, sampled_weight in zip(sampled_ids, sampled_weights):
        original_weight = original_weights[int(household_id)]
        if household_id == 40:
            assert sampled_weight == original_weight
        else:
            assert sampled_weight >= original_weight

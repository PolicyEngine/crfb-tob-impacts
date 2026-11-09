"""The year runner, and every scorer against hand-composed reforms.

Invariants (see tests/test_scoring_economic_assumption.py for the full list):

1. Order: the static baseline runs under the economic assumption reform and
   then the tax assumption reform; the static reform adds the policy last.
2. Same assumptions on both sides: the reform's reforms begin with exactly
   the baseline's, and a baseline scored under a different economic
   assumption than the dataset's is rejected.
3. Differential: a reform scored on a dataset that build_year calibrated
   under the economic assumption equals the same reform with the assumption
   composed by hand, in static scoring (year runner and full-H5 worker) and in
   behavioral scoring (full-H5 worker), on an engine whose results depend on
   the order the reforms apply in.
4. No assumption, no change: without an economic assumption the year runner
   passes the engine exactly the reforms it passed before.
5. Aggregation differences a full-H5 cell only against a baseline scored
   under the same economic assumption.
"""

from __future__ import annotations

import json
import sys

import pytest

from src import year_runner  # first, so it binds the real src.engine
from src import pipeline
from src import reform_full_h5_worker as worker
from src import tax_assumption_loader as loader
from tests import pipeline_fakes as fakes
from tests import scoring_fakes as sf
from tests.pipeline_fakes import FakeEconomicReform, FakeTaxReform, flatten_reform
from tests.scoring_fakes import FakePolicyReform

YEAR = 2050
WRONG_SHA = "0" * 64
NUMERIC_RESULT_KEYS = (
    "baseline_revenue",
    "reform_revenue",
    "revenue_impact",
    "baseline_tob_oasdi",
    "reform_tob_oasdi",
    "tob_oasdi_impact",
    "baseline_tob_medicare_hi",
    "reform_tob_medicare_hi",
    "tob_medicare_hi_impact",
    "tob_total_impact",
    "employer_ss_tax_revenue",
    "employer_medicare_tax_revenue",
    "oasdi_net_impact",
    "hi_net_impact",
)


@pytest.fixture(autouse=True)
def _fake_tax_reform(monkeypatch):
    sf.patch_tax_reform(monkeypatch)


def _record_scenarios(monkeypatch, frame=None) -> list:
    """Replace the engine run with one that records each reform it gets."""
    reforms: list = []

    def compute(*, year, dataset_name, reform, progress_label):
        reforms.append(reform)
        if frame is None:
            return None, year_runner.ScenarioAggregate(*([1.0] * 8))
        return None, sf.fake_aggregate(frame, year, reform)

    monkeypatch.setattr(
        year_runner, "compute_scenario_household_metrics_and_aggregate", compute
    )
    return reforms


def _score_static(dataset, year, reform_functions=None):
    baseline = year_runner.load_baseline(year, dataset)
    result = year_runner.compute_reform_result(
        reform_id="option1",
        year=year,
        scoring_type="static",
        dataset_name=dataset,
        baseline=baseline,
        reform_functions=reform_functions or {"option1": lambda: FakePolicyReform},
        behavioral_functions={},
        employer_net_reforms=frozenset({"option1"}),
    )
    return baseline, result


# ---------------------------------------------------------------------------
# Order and agreement
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("year", [2030, 2050])
def test_static_baseline_and_reform_compose_economic_tax_then_policy(
    monkeypatch, tmp_path, year
):
    dataset = sf.write_dataset(tmp_path, year, economic=sf.economic_record())
    reforms = _record_scenarios(monkeypatch)

    baseline, result = _score_static(dataset, year)

    base, scored = (flatten_reform(reform) for reform in reforms)
    assumptions = (
        (FakeEconomicReform, FakeTaxReform) if year >= 2035 else (FakeEconomicReform,)
    )
    assert base == assumptions
    assert scored == (*assumptions, FakePolicyReform)
    assert scored[: len(base)] == base
    sha = sf.sha256(fakes.__file__)
    assert baseline.economic_assumption_reform == sf.ECONOMIC_SPEC
    assert baseline.economic_assumption_module_sha256 == sha
    assert result["baseline_economic_assumption_reform"] == sf.ECONOMIC_SPEC
    assert result["baseline_economic_assumption_module_sha256"] == sha
    assert year_runner.baseline_result_to_dict(baseline)[
        "economic_assumption_reform"
    ] == (sf.ECONOMIC_SPEC)


def test_reform_scoring_rejects_a_baseline_without_the_economic_assumption(
    monkeypatch, tmp_path
):
    dataset = sf.write_dataset(tmp_path, YEAR, economic=sf.economic_record())
    reforms = _record_scenarios(monkeypatch)
    baseline = year_runner.BaselineResult(
        *([1.0] * 6),
        tax_assumption_name=sf.TAX_NAME,
        tax_assumption_active=True,
    )
    with pytest.raises(ValueError, match="economic assumption does not match"):
        year_runner.compute_reform_result(
            reform_id="option1",
            year=YEAR,
            scoring_type="static",
            dataset_name=dataset,
            baseline=baseline,
            reform_functions={"option1": lambda: FakePolicyReform},
            behavioral_functions={},
            employer_net_reforms=frozenset(),
        )
    assert reforms == []


def test_reform_scoring_rejects_a_baseline_with_an_assumption_the_dataset_lacks(
    monkeypatch, tmp_path
):
    dataset = sf.write_dataset(tmp_path, YEAR, economic=None)
    _record_scenarios(monkeypatch)
    baseline = year_runner.BaselineResult(
        *([1.0] * 6),
        tax_assumption_name=sf.TAX_NAME,
        tax_assumption_active=True,
        economic_assumption_reform=sf.ECONOMIC_SPEC,
        economic_assumption_module_sha256=sf.sha256(fakes.__file__),
    )
    with pytest.raises(ValueError, match="economic assumption does not match"):
        year_runner.compute_reform_result(
            reform_id="option1",
            year=YEAR,
            scoring_type="static",
            dataset_name=dataset,
            baseline=baseline,
            reform_functions={"option1": lambda: FakePolicyReform},
            behavioral_functions={},
            employer_net_reforms=frozenset(),
        )


def test_a_baseline_read_back_from_a_result_row_without_an_assumption_passes(
    monkeypatch, tmp_path
):
    # Result rows write a missing assumption as "", and a baseline rebuilt
    # from such a row must still match a dataset without one.
    dataset = sf.write_dataset(tmp_path, YEAR, economic=None)
    reforms = _record_scenarios(monkeypatch)
    baseline = year_runner.BaselineResult(
        *([1.0] * 6),
        tax_assumption_name=sf.TAX_NAME,
        tax_assumption_active=True,
        economic_assumption_reform="",
        economic_assumption_module_sha256="",
    )
    year_runner.compute_reform_result(
        reform_id="option1",
        year=YEAR,
        scoring_type="static",
        dataset_name=dataset,
        baseline=baseline,
        reform_functions={"option1": lambda: FakePolicyReform},
        behavioral_functions={},
        employer_net_reforms=frozenset(),
    )
    assert reforms == [(FakeTaxReform, FakePolicyReform)]


def test_year_runner_behavioral_scoring_refuses_the_economic_assumption(
    monkeypatch, tmp_path
):
    # Its baseline branch carries no reform, so the response would treat the
    # assumption as policy; the full-H5 worker is the behavioral path.
    dataset = sf.write_dataset(tmp_path, YEAR, economic=sf.economic_record())
    reforms = _record_scenarios(monkeypatch)
    baseline = year_runner.load_baseline(YEAR, dataset)
    with pytest.raises(ValueError, match="full-H5 worker"):
        year_runner.compute_reform_result(
            reform_id="option1",
            year=YEAR,
            scoring_type="behavioral",
            dataset_name=dataset,
            baseline=baseline,
            reform_functions={},
            behavioral_functions={"option1": lambda: FakePolicyReform},
            employer_net_reforms=frozenset(),
        )
    assert len(reforms) == 1  # the baseline only


def test_an_explicit_baseline_reform_cannot_replace_the_recorded_assumption(
    monkeypatch, tmp_path
):
    dataset = sf.write_dataset(tmp_path, YEAR, economic=sf.economic_record())
    _record_scenarios(monkeypatch)
    with pytest.raises(ValueError, match="explicit baseline reform"):
        year_runner.load_baseline(YEAR, dataset, baseline_reform=FakePolicyReform)


def test_year_runner_refuses_a_changed_module_hash(monkeypatch, tmp_path):
    dataset = sf.write_dataset(
        tmp_path, YEAR, economic=sf.economic_record(module_sha256=WRONG_SHA)
    )
    reforms = _record_scenarios(monkeypatch)
    with pytest.raises(ValueError) as error:
        year_runner.load_baseline(YEAR, dataset)
    assert WRONG_SHA in str(error.value)
    assert sf.sha256(fakes.__file__) in str(error.value)
    assert reforms == []


@pytest.mark.parametrize("year", [2030, 2050])
def test_year_runner_without_an_economic_assumption_scores_as_before(
    monkeypatch, tmp_path, year
):
    dataset = sf.write_dataset(tmp_path, year, economic=None)
    reforms = _record_scenarios(monkeypatch)

    baseline, result = _score_static(dataset, year)

    if year >= 2035:
        assert reforms == [FakeTaxReform, (FakeTaxReform, FakePolicyReform)]
        assert reforms[0] is loader.load_tax_assumption_reform_for_dataset(
            dataset, year
        )
    else:
        assert reforms == [None, FakePolicyReform]
    assert baseline.economic_assumption_reform is None
    assert baseline.economic_assumption_module_sha256 is None
    assert result["baseline_economic_assumption_reform"] == ""
    assert result["baseline_economic_assumption_module_sha256"] == ""


# ---------------------------------------------------------------------------
# Differential: scored from metadata vs composed by hand
# ---------------------------------------------------------------------------


def _growth_rates():
    return {
        f"calibration.fake.{name}": 0.02
        for name in fakes.frame_variable_names() + list(pipeline.KNOWN_ABSENT_INPUTS)
    }


def _build_with_assumption(monkeypatch, tmp_path):
    """Calibrate a year under the economic assumption with build_year."""
    engine = fakes.FakeEngine(YEAR, fakes.make_frame(YEAR, seed=5), _growth_rates())
    fakes.install(monkeypatch, engine, tax_reform=FakeTaxReform)
    pipeline.build_year(
        YEAR,
        "fake-base",
        tmp_path,
        base_dataset_label="fake-base",
        economic_assumption_reform=FakeEconomicReform,
        economic_assumption_metadata=pipeline.economic_assumption_provenance(
            sf.ECONOMIC_SPEC
        ),
    )
    dataset = tmp_path / f"{YEAR}.h5"
    metadata = json.loads((tmp_path / f"{YEAR}.h5.metadata.json").read_text())
    # The build's own simulations ran under the assumption, ahead of the tax
    # assumption wherever that applied.
    for stage, reform in engine.constructed:
        assert flatten_reform(reform)[0] is FakeEconomicReform, stage
    return dataset, engine.written[str(dataset)], metadata


def _by_hand(frame, *, behavioral=False, economic=True):
    """The result row with every reform composed explicitly."""
    assumptions = (FakeEconomicReform, FakeTaxReform) if economic else (FakeTaxReform,)
    base = sf.fake_aggregate(frame, YEAR, assumptions)
    scored = sf.fake_aggregate(
        frame,
        YEAR,
        (*assumptions, FakePolicyReform),
        baseline_reform=assumptions if behavioral else None,
    )
    baseline = year_runner.baseline_result_from_aggregate(
        base, tax_assumption_name=sf.TAX_NAME, tax_assumption_active=True
    )
    return year_runner.build_reform_result_from_aggregates(
        reform_id="option1",
        year=YEAR,
        baseline=baseline,
        reform_totals=scored,
        employer_net_reforms=frozenset({"option1"}),
    )


def _assert_same_numbers(actual, expected):
    for key in NUMERIC_RESULT_KEYS:
        assert actual[key] == pytest.approx(expected[key], rel=1e-12), key


def test_static_scoring_from_metadata_equals_hand_composition(monkeypatch, tmp_path):
    dataset, frame, metadata = _build_with_assumption(monkeypatch, tmp_path)
    assert metadata["economic_assumption"]["reform"] == sf.ECONOMIC_SPEC
    assert metadata["economic_assumption"]["module_sha256"] == sf.sha256(fakes.__file__)
    _record_scenarios(monkeypatch, frame)

    baseline, year_runner_row = _score_static(dataset, YEAR)
    by_hand = _by_hand(frame)
    _assert_same_numbers(year_runner_row, by_hand)

    # The full-H5 worker's reform simulation, aggregated against the same
    # static baseline, gives the same row.
    constructed = sf.patch_worker(monkeypatch, worker, frame=frame, year=YEAR)
    sf.run_worker(worker, dataset, YEAR, "static", tmp_path / "out")
    (sim,) = constructed
    worker_row = year_runner.build_reform_result_from_aggregates(
        reform_id="option1",
        year=YEAR,
        baseline=baseline,
        reform_totals=sf.fake_aggregate(frame, YEAR, sim.reform),
        employer_net_reforms=frozenset({"option1"}),
    )
    _assert_same_numbers(worker_row, by_hand)

    # The comparison has power: dropping any reform, or swapping two, changes
    # the reform simulation's totals.
    without = _by_hand(frame, economic=False)
    assert without["employer_ss_tax_revenue"] != pytest.approx(
        by_hand["employer_ss_tax_revenue"]
    )
    ordered = sf.fake_aggregate(
        frame, YEAR, (FakeEconomicReform, FakeTaxReform, FakePolicyReform)
    )
    for wrong in (
        (FakePolicyReform, FakeEconomicReform, FakeTaxReform),
        (FakeTaxReform, FakeEconomicReform, FakePolicyReform),
        (FakeEconomicReform, FakePolicyReform),
        (FakeTaxReform, FakePolicyReform),
        (FakeEconomicReform, FakeTaxReform),
    ):
        totals = sf.fake_aggregate(frame, YEAR, wrong)
        assert (totals.taxable_payroll, totals.tob_total) != (
            pytest.approx(ordered.taxable_payroll),
            pytest.approx(ordered.tob_total),
        ), wrong


def test_behavioral_scoring_from_metadata_equals_hand_composition(
    monkeypatch, tmp_path
):
    dataset, frame, _ = _build_with_assumption(monkeypatch, tmp_path)
    _record_scenarios(monkeypatch, frame)
    baseline = year_runner.load_baseline(YEAR, dataset)

    constructed = sf.patch_worker(monkeypatch, worker, frame=frame, year=YEAR)
    sf.run_worker(worker, dataset, YEAR, "behavioral", tmp_path / "out")
    (sim,) = constructed
    worker_row = year_runner.build_reform_result_from_aggregates(
        reform_id="option1",
        year=YEAR,
        baseline=baseline,
        reform_totals=sf.fake_aggregate(
            frame, YEAR, sim.reform, baseline_reform=sim.baseline.reform
        ),
        employer_net_reforms=frozenset({"option1"}),
    )
    by_hand = _by_hand(frame, behavioral=True)
    _assert_same_numbers(worker_row, by_hand)

    # A baseline branch without the assumption would respond to it as policy.
    assumption_as_policy = sf.fake_aggregate(
        frame,
        YEAR,
        (FakeEconomicReform, FakeTaxReform, FakePolicyReform),
        baseline_reform=(FakeTaxReform,),
    )
    assert assumption_as_policy.revenue != pytest.approx(by_hand["reform_revenue"])


def test_year_runner_module_binds_the_real_engine():
    # Guards the import order above: the fakes replace src.engine in
    # sys.modules, and year_runner must not have bound a fake.
    assert year_runner.dataset_microsimulation.__module__ == "src.engine"
    assert sys.modules["src.engine"].dataset_microsimulation is (
        year_runner.dataset_microsimulation
    )


# ---------------------------------------------------------------------------
# Full-H5 aggregation pairs each cell with a baseline under the same assumption
# ---------------------------------------------------------------------------

SCENARIO_URI = "r2://bucket/run/reform_full_h5/year=2050/reform=option1/scenario.h5"


def _aggregate(monkeypatch, tmp_path, *, cell_economic, baseline_economic):
    import pandas as pd

    from scripts import aggregate_reform_full_h5_results as agg

    status = tmp_path / "status.csv"
    pd.DataFrame(
        [
            {
                "year": YEAR,
                "reform_name": "option1",
                "reform_h5_status": "complete",
                "scenario_h5_uri": SCENARIO_URI,
                "metadata_uri": "",
                "output_h5_sha256": "",
                "scoring_type": "static",
            }
        ]
    ).to_csv(status, index=False)
    baseline_row = {
        "year": YEAR,
        "baseline_revenue": 10.0,
        "baseline_tob_medicare_hi": 1.0,
        "baseline_tob_oasdi": 2.0,
        "baseline_tob_total": 3.0,
        "baseline_tax_assumption_name": sf.TAX_NAME,
        "baseline_tax_assumption_active": True,
    }
    if baseline_economic:
        baseline_row["baseline_economic_assumption_reform"] = sf.ECONOMIC_SPEC
        baseline_row["baseline_economic_assumption_module_sha256"] = sf.sha256(
            fakes.__file__
        )
    existing = tmp_path / "results.csv"
    pd.DataFrame([baseline_row]).to_csv(existing, index=False)
    cell_metadata = {
        "economic_assumption": (
            loader.economic_assumption_output_metadata(
                loader.economic_assumption_contract_from_metadata(
                    {"economic_assumption": sf.economic_record()}
                )
            )
            if cell_economic
            else {"active": False, "reform": None}
        )
    }
    downloaded: list = []

    def download(*, client, obj, cache_dir, expected_sha256):
        downloaded.append(obj.key)
        path = tmp_path / "cache" / obj.key
        path.parent.mkdir(parents=True, exist_ok=True)
        if obj.key.endswith("metadata.json"):
            path.write_text(json.dumps(cell_metadata))
        else:
            path.write_bytes(b"scenario")
        return path

    monkeypatch.setattr(agg, "_r2_client_from_env", lambda: object())
    monkeypatch.setattr(agg, "_download_r2_object", download)
    monkeypatch.setattr(
        agg,
        "_aggregate_full_output_h5",
        lambda path: year_runner.ScenarioAggregate(*([20.0] * 8)),
    )
    output = tmp_path / "out.csv"
    agg.aggregate_live_full_h5_results(
        live_status_path=status,
        existing_results_path=existing,
        baseline_dir=tmp_path / "no-baselines",
        cache_dir=tmp_path / "cache",
        output_path=output,
        summary_path=tmp_path / "summary.json",
        compute_missing_baselines=False,
        limit=None,
    )
    return pd.read_csv(output, keep_default_na=False), downloaded


@pytest.mark.parametrize(
    "cell_economic,baseline_economic",
    [(True, False), (False, True)],
    ids=["cell-only", "baseline-only"],
)
def test_aggregation_refuses_a_cell_and_baseline_under_different_assumptions(
    monkeypatch, tmp_path, cell_economic, baseline_economic
):
    with pytest.raises(ValueError, match="refusing to difference"):
        _aggregate(
            monkeypatch,
            tmp_path,
            cell_economic=cell_economic,
            baseline_economic=baseline_economic,
        )


def test_aggregation_pairs_a_cell_with_a_baseline_under_the_same_assumption(
    monkeypatch, tmp_path
):
    rows, _ = _aggregate(
        monkeypatch, tmp_path, cell_economic=True, baseline_economic=True
    )
    (row,) = rows.to_dict(orient="records")
    assert row["baseline_economic_assumption_reform"] == sf.ECONOMIC_SPEC
    assert row["revenue_impact"] == pytest.approx(10.0)


def test_aggregation_without_an_economic_assumption_is_unchanged(monkeypatch, tmp_path):
    rows, downloaded = _aggregate(
        monkeypatch, tmp_path, cell_economic=False, baseline_economic=False
    )
    (row,) = rows.to_dict(orient="records")
    assert row["revenue_impact"] == pytest.approx(10.0)
    assert row["baseline_economic_assumption_reform"] == ""
    # With no metadata_uri recorded, the metadata sits beside scenario.h5.
    assert downloaded == [
        "run/reform_full_h5/year=2050/reform=option1/scenario.h5",
        "run/reform_full_h5/year=2050/reform=option1/metadata.json",
    ]

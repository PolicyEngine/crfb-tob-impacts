"""The chunked worker writes the same tables as a whole-file simulation."""

import numpy as np
import pandas as pd
import pytest

from src import pipeline
from src import reform_full_h5_worker as worker
from src.reform_full_h5_output_manifest import full_h5_output_variable_manifest
from src.tax_assumption_loader import compose_reforms
from tests.test_household_vectors import YEAR, year_file  # noqa: F401

TRUSTEES = (
    "policyengine_us.reforms.ssa.trustees_2026:"
    "trustees_2026_economic_assumptions_reform"
)


def _reform(scoring_type):
    return worker.build_policy_reform("option1", scoring_type)


def _simulation(dataset, reform, scoring_type, baseline_reform=None):
    from policyengine_us import Microsimulation

    sim = Microsimulation(dataset=dataset, reform=reform)
    if scoring_type == "behavioral":
        worker.install_behavioral_baseline_tax_system(
            sim, baseline_reform=baseline_reform
        )
    return sim


def _assert_same_tables(left, right):
    for entity in full_h5_output_variable_manifest():
        whole = pd.read_hdf(left, entity)
        chunked = pd.read_hdf(right, entity)
        assert list(chunked.columns) == list(whole.columns)
        assert len(chunked) == len(whole)
        for name in whole:
            np.testing.assert_allclose(
                chunked[name].to_numpy(dtype=float),
                whole[name].to_numpy(dtype=float),
                rtol=1e-5,
                atol=0.01,
                err_msg=f"{entity}.{name}",
            )


@pytest.mark.parametrize("n_chunks", [1, 2, 3])
def test_chunked_tables_match_the_whole_file(year_file, tmp_path, n_chunks):  # noqa: F811
    _, path = year_file
    reform = _reform("static")
    whole = tmp_path / "whole.h5"
    chunked = tmp_path / "chunked.h5"
    worker.save_complete_microsimulation_h5(
        _simulation(str(path), reform, "static"), whole, year=YEAR
    )
    metadata = worker.save_chunked_microsimulation_h5(
        lambda dataset: _simulation(dataset, reform, "static"),
        path,
        chunked,
        year=YEAR,
        n_chunks=n_chunks,
    )
    _assert_same_tables(whole, chunked)
    assert metadata["household_chunks"] == n_chunks
    assert metadata["tob_materialization"]["materialized"] == [
        "tob_revenue_medicare_hi",
        "tob_revenue_oasdi",
    ]


def test_behavioral_chunks_match_the_whole_file(year_file, tmp_path):  # noqa: F811
    _, path = year_file
    economic = pipeline.load_economic_assumption_reform(TRUSTEES)
    reform = compose_reforms(economic, _reform("behavioral"))
    whole = tmp_path / "whole.h5"
    chunked = tmp_path / "chunked.h5"
    worker.save_complete_microsimulation_h5(
        _simulation(str(path), reform, "behavioral", economic), whole, year=YEAR
    )
    worker.save_chunked_microsimulation_h5(
        lambda dataset: _simulation(dataset, reform, "behavioral", economic),
        path,
        chunked,
        year=YEAR,
        n_chunks=2,
    )
    _assert_same_tables(whole, chunked)


def test_behavioral_baseline_sees_a_redefined_variable(year_file):  # noqa: F811
    from policyengine_core.reforms import Reform
    from policyengine_us.model_api import YEAR as ANNUAL
    from policyengine_us.model_api import Person, Variable

    class charitable_cash_donations(Variable):
        value_type = float
        entity = Person
        label = "Charitable cash donations"
        definition_period = ANNUAL
        default_value = 10.0

    class redefined(Reform):
        def apply(self):
            self.update_variable(charitable_cash_donations)

    _, path = year_file
    sim = _simulation(str(path), redefined, "behavioral", redefined)
    values = sim.baseline.calculate("charitable_cash_donations", YEAR)
    np.testing.assert_array_equal(values, 10.0)


def test_a_failing_variable_stops_the_cell(year_file, tmp_path):  # noqa: F811
    _, path = year_file
    with pytest.raises(ValueError, match="medicaid_slcsp"):
        worker.save_chunked_microsimulation_h5(
            lambda dataset: _simulation(dataset, None, "static"),
            path,
            tmp_path / "chunked.h5",
            year=YEAR,
            variables_by_entity={"person": ["person_id", "medicaid"]},
            n_chunks=2,
        )
    assert not (tmp_path / "chunked.h5").exists()

"""Chunked household vectors agree with a whole-file simulation."""

import sys

import numpy as np
import pandas as pd
import pytest

from src import pipeline
from tests.test_stage_a_aging import load_engine

YEAR = 2050
VARIABLES = (
    "social_security",
    "taxable_earnings_for_social_security",
    "tob_revenue_oasdi",
    "tob_revenue_medicare_hi",
    "income_tax",
    "adjusted_gross_income",
)


@pytest.fixture
def year_file(tmp_path, monkeypatch):
    pytest.importorskip("policyengine_us.tools.calculate_chunked")
    engine = load_engine(monkeypatch)
    monkeypatch.setattr(engine, "_require_certified_runtime", lambda: None)
    monkeypatch.setitem(sys.modules, "src.engine", engine)
    # Household 30 holds two tax units, and household 20 one couple. Group ids
    # run out of order, so sorting by id can't line tables up by accident.
    household = np.array([10, 20, 20, 30, 30, 40])
    tax_unit = np.array([9, 2, 2, 7, 4, 1])
    frame = pd.DataFrame(
        {
            f"person_id__{YEAR}": [101, 102, 103, 104, 105, 106],
            f"age__{YEAR}": [70, 72, 68, 45, 19, 80],
            f"household_weight__{YEAR}": [2.0, 3.0, 3.0, 4.0, 4.0, 5.0],
            f"employment_income_before_lsr__{YEAR}": [
                0.0,
                60_000.0,
                0.0,
                400_000.0,
                8_000.0,
                0.0,
            ],
            f"social_security_retirement_reported__{YEAR}": [
                90_000.0,
                70_000.0,
                40_000.0,
                0.0,
                0.0,
                120_000.0,
            ],
            f"taxable_private_pension_income__{YEAR}": [
                300_000.0,
                90_000.0,
                0.0,
                0.0,
                0.0,
                50_000.0,
            ],
        }
    )
    for entity, ids in {
        "household": household,
        "family": household,
        "spm_unit": household,
        "tax_unit": tax_unit,
        "marital_unit": np.array([1, 2, 2, 3, 4, 5]),
    }.items():
        frame[f"{entity}_id__{YEAR}"] = ids
        frame[f"person_{entity}_id__{YEAR}"] = ids
    path = tmp_path / f"{YEAR}.h5"
    pipeline.write_year_h5(frame, YEAR, path)
    return engine, path


def _whole_file(path, reform=None):
    from policyengine_us import Microsimulation

    sim = Microsimulation(dataset=str(path), reform=reform)
    return {
        name: np.asarray(
            sim.calculate(name, period=YEAR, map_to="household").values, dtype=float
        )
        for name in VARIABLES
    }


@pytest.mark.parametrize("n_chunks", [1, 2, 3])
def test_chunked_vectors_match_the_whole_file(year_file, n_chunks):
    engine, path = year_file
    whole = _whole_file(path)
    chunked = engine.household_vectors(path, YEAR, VARIABLES, n_chunks=n_chunks)
    assert sum(values.sum() for name, values in whole.items() if "tob" in name) > 0
    for name in VARIABLES:
        np.testing.assert_allclose(chunked[name], whole[name], rtol=1e-5, atol=0.01)


def test_chunking_leaves_room_for_the_guards_frames(year_file):
    engine, path = year_file
    before = sys.getrecursionlimit()
    sys.setrecursionlimit(1000)
    try:
        engine.chunked_entity_tables(
            path, YEAR, ["age"], engine.frame_microsimulation, n_chunks=1
        )
        assert sys.getrecursionlimit() >= engine.CHUNKED_RECURSION_LIMIT
    finally:
        sys.setrecursionlimit(before)


def test_the_reform_reaches_every_chunk(year_file):
    from policyengine_core.reforms import Reform

    engine, path = year_file

    class LowCap(Reform):
        def apply(self):
            def modify(parameters):
                parameters.get_child("gov.irs.payroll.social_security.cap").update(
                    period=str(YEAR), value=10_000.0
                )
                return parameters

            self.modify_parameters(modify)

    chunked = engine.household_vectors(path, YEAR, VARIABLES, reform=LowCap, n_chunks=2)
    whole = _whole_file(path, reform=LowCap)
    baseline = _whole_file(path)
    name = "taxable_earnings_for_social_security"
    assert chunked[name].sum() < baseline[name].sum()
    np.testing.assert_allclose(chunked[name], whole[name], rtol=1e-5, atol=0.01)


def test_year_file_keeps_entity_rows_and_decodes_strings(year_file, tmp_path):
    import h5py

    engine, path = year_file
    with h5py.File(path, "r+") as handle:
        handle.create_dataset(
            f"county_fips/{YEAR}", data=np.array([b"06037"] * 4, dtype="S5")
        )
    single = engine.year_file_dataset(path, YEAR).get_year(YEAR)
    assert len(single.person) == 6
    assert len(single.household) == 4
    assert len(single.tax_unit) == 5
    assert single.household.county_fips.tolist() == ["06037"] * 4

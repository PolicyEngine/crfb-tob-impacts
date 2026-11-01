"""Exercise the real year writer and engine on a synthetic person frame."""

import sys
from types import SimpleNamespace

import h5py
import numpy as np
import pandas as pd
import pytest

from src import pipeline


def test_reported_benefits_survive_real_year_writer(tmp_path, monkeypatch):
    engine = pytest.importorskip("policyengine_us")
    from policyengine_core.data.dataset import Dataset
    from policyengine_us.system import system

    reported = pipeline.SOCIAL_SECURITY_SCALE_CANDIDATES
    if any(name not in system.variables for name in reported):
        pytest.skip("The installed engine predates reported benefit inputs")

    year = 2050
    frame = pd.DataFrame(
        {
            **{
                f"{name}__{year}": [100, 200]
                for name in pipeline.PERSON_LEVEL_IDENTITY_INPUTS
            },
            f"age__{year}": [70, 72],
            f"household_weight__{year}": [2.0, 3.0],
            **{
                f"{name}__{year}": [1_000.0 * index, 2_000.0 * index]
                for index, name in enumerate(reported, start=1)
            },
        }
    )

    def frame_simulation(dataset, reform=None):
        return engine.Microsimulation(dataset=dataset, reform=reform)

    # Replace only the runtime gate; dataframe loading, holders, H5 writing and
    # the simulation reloaded from the H5 remain real.
    monkeypatch.setitem(
        sys.modules,
        "src.engine",
        SimpleNamespace(frame_microsimulation=frame_simulation),
    )
    reference = frame_simulation(Dataset.from_dataframe(frame, year))
    benefits = [name.removesuffix("_reported") for name in reported]
    expected = {
        name: np.asarray(reference.calculate(name, period=year)).copy()
        for name in (*benefits, "social_security")
    }
    assert all(values.sum() > 0 for values in expected.values())

    output_path = tmp_path / "2050.h5"
    pipeline.write_year_h5(frame, year, output_path)

    with h5py.File(output_path, "r") as handle:
        for name in reported:
            np.testing.assert_array_equal(
                handle[f"{name}/{year}"][...], frame[f"{name}__{year}"]
            )
        assert all(name not in handle for name in (*benefits, "social_security"))

    reloaded = engine.Microsimulation(dataset=str(output_path))
    for name, values in expected.items():
        np.testing.assert_array_equal(
            np.asarray(reloaded.calculate(name, period=year)), values
        )

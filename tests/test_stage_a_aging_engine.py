"""Real-engine agreement between reformed input aging and category caps."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src import pipeline
from tests.test_stage_a_aging import entity_file, load_engine


@pytest.fixture(scope="module")
def aged_frames(tmp_path_factory, request):
    pytest.importorskip("policyengine_us.data.economic_assumptions")
    from policyengine_core.reforms import Reform
    from policyengine_us import Microsimulation
    from policyengine_us.data import economic_assumptions
    from policyengine_us.data.dataset_schema import USSingleYearDataset
    from policyengine_us.data.economic_assumptions import extend_single_year_dataset
    from policyengine_us.system import system

    if not getattr(system, "_per_capita_uprating_built", False):
        pytest.skip("requires the per-capita dataset extension API")
    path = entity_file(tmp_path_factory.mktemp("aging") / "base.h5")
    names = pipeline.GROWTH_CAP_VARIABLES
    totals = {
        pipeline.growth_cap_total_parameter(
            pipeline.growth_cap_uprating_parameter(name, system.variables),
            system.parameters,
        )
        for name in names
    }
    total_values = {
        name: {
            year: float(system.parameters.get_child(name)(f"{year}-01-01"))
            for year in range(2035, 2051)
        }
        for name in totals
    }

    class DoubleGrowth(Reform):
        def apply(self):
            def modify(parameters):
                for name, values in total_values.items():
                    parameter = parameters.get_child(name)
                    for year, value in values.items():
                        parameter.update(period=str(year), value=2 * value)
                return parameters

            self.modify_parameters(modify)

    with pd.HDFStore(path, "a") as store:
        person = store["person"]
        for name in names:
            person[name] = np.array([100.0, 200.0, 300.0])
        store["person"] = person
    monkeypatch = pytest.MonkeyPatch()
    request.addfinalizer(monkeypatch.undo)
    engine = load_engine(monkeypatch)
    monkeypatch.setattr(engine, "_require_certified_runtime", lambda: None)
    aging_systems = []

    def record_extension(dataset, **kwargs):
        if kwargs.get("system") is not None:
            aging_systems.append(kwargs["system"])
        return extend_single_year_dataset(dataset, **kwargs)

    monkeypatch.setattr(
        economic_assumptions, "extend_single_year_dataset", record_extension
    )
    sim = engine.stage_a_microsimulation(path, 2050, reform=DoubleGrowth)
    default = Microsimulation(dataset=str(path), dataset_end_year=2050)
    # Keep the real constructor's system for the separate manual dataset.
    (reformed_system,) = aging_systems
    manual_dataset = extend_single_year_dataset(
        USSingleYearDataset(file_path=str(path)), end_year=2050, system=reformed_system
    )
    manual = Microsimulation(dataset=manual_dataset, reform=DoubleGrowth)
    yield {
        "sim": sim,
        "default": default,
        "manual": manual,
        "system": reformed_system,
        "frame": pipeline.materialize_year_frame(sim, 2050),
        "path": path,
    }


def test_frame_matches_manually_extended_simulation(aged_frames):
    data = aged_frames
    pd.testing.assert_frame_equal(
        data["frame"],
        pipeline.materialize_year_frame(data["manual"], 2050),
        check_exact=True,
    )
    for name in pipeline.GROWTH_CAP_VARIABLES:
        np.testing.assert_array_equal(
            data["frame"][f"{name}__2050"],
            data["manual"].calculate(name, period=2050).values,
        )
    assert int(data["sim"].default_calculation_period) == 2024
    np.testing.assert_array_equal(data["frame"]["person_id__2050"], [10, 20, 30])
    assert data["sim"].dataset.years[-1] == 2050


def test_reformed_national_growth_agrees_with_frame_and_cap(aged_frames):
    from microdf import MicroDataFrame

    sim = aged_frames["sim"]
    frame = aged_frames["frame"].copy()
    reference = pipeline.materialize_year_frame(sim, 2034)
    weighted = MicroDataFrame(frame, weights=frame["household_weight__2050"].to_numpy())
    reference = MicroDataFrame(
        reference, weights=reference["household_weight__2034"].to_numpy()
    )
    gdp = pipeline._tr2026_gdp_growth(2034, 2050)
    expected = {}
    for name in pipeline.GROWTH_CAP_VARIABLES:
        total = pipeline.growth_cap_total_parameter(
            pipeline.growth_cap_uprating_parameter(
                name, sim.tax_benefit_system.variables
            ),
            sim.tax_benefit_system.parameters,
        )
        parameter = sim.tax_benefit_system.parameters.get_child(total)
        growth = float(parameter("2050-01-01") / parameter("2034-01-01"))
        base = float(reference[f"{name}__2034"].sum())
        assert float(weighted[f"{name}__2050"].sum()) / base == pytest.approx(
            growth, rel=2e-6
        )
        # The fake doubles growth relative to the default total series.
        default_total = aged_frames["default"].tax_benefit_system.parameters.get_child(
            total
        )
        assert growth == pytest.approx(
            2 * float(default_total("2050-01-01") / default_total("2034-01-01"))
        )
        expected[name] = base * min(growth, gdp)
    pipeline.cap_longrun_income_growth(frame, sim, 2050)
    capped = MicroDataFrame(frame, weights=frame["household_weight__2050"].to_numpy())
    for name, target in expected.items():
        assert float(capped[f"{name}__2050"].sum()) == pytest.approx(target, rel=2e-6)


def test_only_uprated_columns_move_and_all_base_values_are_identical(aged_frames):
    from policyengine_us.data.dataset_schema import USSingleYearDataset

    sim, default = aged_frames["sim"], aged_frames["default"]
    original = USSingleYearDataset(file_path=str(aged_frames["path"]))
    for entity, table in zip(original.table_names, original.tables):
        pd.testing.assert_frame_equal(
            getattr(sim.dataset.get_year(2024), entity), table, check_exact=True
        )
    pd.testing.assert_frame_equal(
        pipeline.materialize_year_frame(sim, 2024),
        pipeline.materialize_year_frame(default, 2024),
        check_exact=True,
    )
    baseline = pipeline.materialize_year_frame(default, 2050)
    moved = []
    for column in aged_frames["frame"].columns:
        if not np.array_equal(aged_frames["frame"][column], baseline[column]):
            name = column.rsplit("__", 1)[0]
            assert sim.tax_benefit_system.variables[name].uprating, name
            moved.append(name)
    assert set(pipeline.GROWTH_CAP_VARIABLES).issubset(moved)

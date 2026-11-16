"""Projection failures must never become stale target-year inputs."""

from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from src import pipeline


class ProjectionSimulation:
    default_calculation_period = 2024

    def __init__(self, failures=()):
        self.failures = set(failures)
        self.calls = []
        self.frame = pd.DataFrame(
            {
                **{
                    f"{name}__2024": [10, 20]
                    for name in pipeline.PERSON_LEVEL_IDENTITY_INPUTS
                },
                "household_weight__2024": [1.0, 2.0],
                "person_weight__2024": [1.0, 2.0],
                "employment_income_before_lsr__2024": [100.0, 200.0],
                "rental_income__2024": [30.0, 40.0],
                "age__2024": [60, 70],
            }
        )
        self.tax_benefit_system = SimpleNamespace(
            variables={
                column.rsplit("__", 1)[0]: SimpleNamespace(adds=None)
                for column in self.frame.columns
            }
        )
        self.input_variables = list(self.tax_benefit_system.variables)

    def to_input_dataframe(self):
        return self.frame.copy(deep=True)

    def calculate(self, name, *, period, map_to=None):
        self.calls.append((name, period, map_to))
        if name in self.failures:
            raise RuntimeError(f"cannot project {name}")
        values = self.frame[f"{name}__2024"].to_numpy(copy=True)
        if period != 2024 and name == "person_id":
            # The real formula numbers rows in years without a stored value.
            values = np.arange(len(values))
        elif period != 2024 and name in (
            "employment_income_before_lsr",
            "rental_income",
        ):
            values *= 2
        elif name == "age":
            values += period - 2024
        weights = [1.0, 2.0] if period == 2024 else [3.0, 4.0]
        return SimpleNamespace(values=values, weights=np.array(weights))


def test_materialization_names_every_failed_projection():
    failures = ("employment_income_before_lsr", "rental_income")
    sim = ProjectionSimulation(failures)

    with pytest.raises(ValueError) as raised:
        pipeline.materialize_year_frame(sim, 2050)

    for variable in failures:
        assert variable in str(raised.value)
        assert f"cannot project {variable}" in str(raised.value)
        assert (variable, 2050, None) in sim.calls


def test_materialization_projects_inputs_ids_and_target_year_weights():
    sim = ProjectionSimulation()
    original = sim.frame.copy(deep=True)

    frame = pipeline.materialize_year_frame(sim, 2050)

    assert all(column.endswith("__2050") for column in frame)
    np.testing.assert_array_equal(
        frame["employment_income_before_lsr__2050"], [200.0, 400.0]
    )
    np.testing.assert_array_equal(frame["rental_income__2050"], [60.0, 80.0])
    np.testing.assert_array_equal(frame["age__2050"], [86, 96])
    np.testing.assert_array_equal(frame["household_weight__2050"], [3.0, 4.0])
    for variable in pipeline.PERSON_LEVEL_IDENTITY_INPUTS:
        np.testing.assert_array_equal(frame[f"{variable}__2050"], [10, 20])
        if variable != "person_id":
            assert (variable, 2050, None) in sim.calls
    assert ("person_id", 2050, None) not in sim.calls
    assert ("household_id", 2050, "household") in sim.calls
    assert "person_weight__2050" not in frame
    pd.testing.assert_frame_equal(sim.frame, original)


def test_materialization_preserves_every_base_year_input():
    sim = ProjectionSimulation()

    frame = pipeline.materialize_year_frame(sim, 2024)

    expected = sim.frame.drop(columns="person_weight__2024")
    pd.testing.assert_frame_equal(frame, expected)


def test_group_projection_uses_target_year_entity_ids():
    calls = []

    def calculate(name, *, period, map_to=None):
        calls.append((name, period, map_to))
        values = [400.0, 200.0] if name == "group_input" else [20, 10]
        return SimpleNamespace(values=np.array(values))

    sim = SimpleNamespace(
        calculate=calculate,
        tax_benefit_system=SimpleNamespace(
            variables={
                "group_input": SimpleNamespace(entity=SimpleNamespace(key="household"))
            }
        ),
    )
    frame = pd.DataFrame({"person_household_id__2024": [10, 20, 10]})

    projected = pipeline._project_variable_to_person_rows(
        sim, frame, var_name="group_input", year=2050, base_period=2024
    )

    np.testing.assert_array_equal(projected, [200.0, 400.0, 200.0])
    assert ("household_id", 2050, "household") in calls

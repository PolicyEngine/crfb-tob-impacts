"""The national-growth cap preserves the input aging agreement."""

import types

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("hypothesis")
from hypothesis import given, settings
from hypothesis import strategies as st

from src import pipeline


@settings(deadline=None)
@given(
    total_growth=st.floats(
        min_value=0.01, max_value=30, allow_nan=False, allow_infinity=False
    ),
    population_growth=st.floats(
        min_value=0.1, max_value=3, allow_nan=False, allow_infinity=False
    ),
)
def test_aged_total_then_cap_equals_lesser_of_category_and_gdp(
    total_growth, population_growth
):
    name = pipeline.GROWTH_CAP_VARIABLES[0]
    per_capita = "fake.total_per_capita"
    total = "fake.total"

    class Series:
        def __init__(self):
            self.metadata = {"derived_from": total}

        def __call__(self, date):
            return 1 if date.startswith("2034") else total_growth

    parameters = types.SimpleNamespace(get_child=lambda path: Series())
    variables = {name: types.SimpleNamespace(uprating=per_capita)}
    sim = types.SimpleNamespace(
        tax_benefit_system=types.SimpleNamespace(
            parameters=parameters, variables=variables
        )
    )
    frame = pd.DataFrame(
        {f"{name}__2050": np.array([100.0, 200.0]) * total_growth / population_growth}
    )
    # Narrow the cap list without a pytest fixture (Hypothesis reuses fixtures).
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(pipeline, "GROWTH_CAP_VARIABLES", (name,))
        pipeline.cap_longrun_income_growth(frame, sim, 2050)
    actual_total = float(frame.iloc[:, 0].sum()) * population_growth
    assert actual_total == pytest.approx(
        300 * min(total_growth, pipeline._tr2026_gdp_growth(2034, 2050))
    )

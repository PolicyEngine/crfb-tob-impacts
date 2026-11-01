"""Entropy calibration finds the unique solution whenever one exists."""

import numpy as np
import pytest

pytest.importorskip("hypothesis")
from hypothesis import given, settings
from hypothesis import strategies as st

from src.projection import calibrate_entropy_constraints


def _problem(seed, rows, spread):
    rng = np.random.default_rng(seed)
    baseline = rng.uniform(1.0, 20.0, rows)
    heavy = rng.lognormal(0, 2.0, rows) * (rng.random(rows) < 0.5)
    A = np.column_stack(
        [np.ones(rows), heavy + 1e-3, heavy * rng.uniform(0.5, 1.5, rows) + 1e-3]
    )
    targets = A.T @ (baseline * np.exp(rng.normal(0, spread, rows)))
    return A, targets, baseline


@settings(deadline=None, max_examples=200)
@given(
    seed=st.integers(0, 2**32 - 1),
    rows=st.integers(12, 60),
    spread=st.floats(0.0, 1.5),
)
def test_feasible_targets_reach_the_entropy_optimum(seed, rows, spread):
    A, targets, baseline = _problem(seed, rows, spread)
    weights, _ = calibrate_entropy_constraints(A, targets, baseline)
    assert (weights > 0).all()
    np.testing.assert_allclose(A.T @ weights, targets, rtol=1e-7)
    # At the optimum the log ratio lies in the span of the constraint columns,
    # which also makes the solution unique and independent of the start.
    ratio = np.log(weights / baseline)
    coefficients = np.linalg.lstsq(A, ratio, rcond=None)[0]
    np.testing.assert_allclose(A @ coefficients, ratio, atol=1e-5)

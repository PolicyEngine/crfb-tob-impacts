from __future__ import annotations

import pytest

from scripts.assemble_reform_panel import behavioral_static_ratio


def test_endpoint_ratio_uses_tolerance_for_near_zero_static_delta():
    with pytest.warns(RuntimeWarning, match="near zero"):
        ratio = behavioral_static_ratio(
            reform_id="option1",
            year=2100,
            static_delta=999_999.0,
            behavioral_delta=50_000_000.0,
        )

    assert ratio == 1.0


def test_endpoint_ratio_uses_actual_ratio_when_static_delta_is_material():
    assert (
        behavioral_static_ratio(
            reform_id="option1",
            year=2100,
            static_delta=100_000_000.0,
            behavioral_delta=95_000_000.0,
        )
        == 0.95
    )


def test_endpoint_ratio_preserves_missing_behavioral_endpoint():
    assert (
        behavioral_static_ratio(
            reform_id="option1",
            year=2100,
            static_delta=100_000_000.0,
            behavioral_delta=None,
        )
        is None
    )

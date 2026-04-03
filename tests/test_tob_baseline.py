from __future__ import annotations

import numpy as np

from src.tob_baseline import (
    HI_METHOD_CURRENT_LAW,
    HI_METHOD_MATCH_OASDI_PCT_CHANGE,
    build_tob_baseline,
    validate_generated_baseline,
)


def test_build_tob_baseline_uses_source_backed_oasdi_series() -> None:
    baseline = build_tob_baseline(HI_METHOD_MATCH_OASDI_PCT_CHANGE)

    row_2026 = baseline.loc[baseline["year"] == 2026].iloc[0]
    assert np.isclose(row_2026["current_law_oasdi_billions"], 76.7901)
    assert np.isclose(row_2026["oasdi_nominal_delta_billions"], -16.2)
    assert np.isclose(row_2026["tob_oasdi_billions"], 60.5901)


def test_hi_bridge_can_hold_current_law_constant() -> None:
    baseline = build_tob_baseline(HI_METHOD_CURRENT_LAW)
    row_2026 = baseline.loc[baseline["year"] == 2026].iloc[0]
    assert np.isclose(row_2026["tob_hi_billions"], 52.1990)


def test_hi_bridge_can_match_oasdi_percentage_change() -> None:
    baseline = build_tob_baseline(HI_METHOD_MATCH_OASDI_PCT_CHANGE)
    row_2026 = baseline.loc[baseline["year"] == 2026].iloc[0]
    assert np.isclose(row_2026["tob_hi_billions"], 41.1868539030)
    assert np.isclose(row_2026["oasdi_share"], 0.5953219833)


def test_generated_baseline_validates() -> None:
    baseline = build_tob_baseline(HI_METHOD_MATCH_OASDI_PCT_CHANGE)
    validate_generated_baseline(baseline)

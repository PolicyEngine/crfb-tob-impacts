"""Piecewise behavioral ratio interpolation over interior exact anchors.

The behavioral display derives non-anchor years by interpolating
behavioral/static ratios between consecutive exact anchors. Originally the
only anchors were the 2026/2100 endpoints; audit finding H-01b added
interior completion anchors (option12@2062, option6@2033) so reforms whose
static path has a policy kink do not get a single 2026->2100 ratio segment
laid across it. These tests pin the segment mechanics on synthetic frames.
"""

from pathlib import Path
import sys

import pandas as pd
import pytest

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.publish_behavioral_endpoint_dashboard_results import (  # noqa: E402
    _behavioral_annual_for_reform,
)
from scripts.publish_full_h5_static_dashboard_results import ANNUAL_YEARS  # noqa: E402


def _static_frame() -> pd.DataFrame:
    # Static revenue_impact rises linearly 100 -> 470 over 2026-2100.
    return pd.DataFrame(
        {
            "year": list(ANNUAL_YEARS),
            "revenue_impact": [100.0 + 5.0 * (y - 2026) for y in ANNUAL_YEARS],
            "tob_oasdi_impact": [60.0 + 3.0 * (y - 2026) for y in ANNUAL_YEARS],
            "tob_medicare_hi_impact": [
                40.0 + 2.0 * (y - 2026) for y in ANNUAL_YEARS
            ],
            "tob_total_impact": [100.0 + 5.0 * (y - 2026) for y in ANNUAL_YEARS],
            "baseline_revenue": [1000.0] * len(ANNUAL_YEARS),
        }
    )


def _anchors(rows: dict[int, float]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "year": list(rows),
            "revenue_impact": list(rows.values()),
            "tob_oasdi_impact": [0.6 * v for v in rows.values()],
            "tob_medicare_hi_impact": [0.4 * v for v in rows.values()],
            "tob_total_impact": list(rows.values()),
            "run_prefix": ["cell"] * len(rows),
            "baseline_source": ["b"] * len(rows),
        }
    )


def _build(anchor_rows: dict[int, float]) -> pd.DataFrame:
    out = _behavioral_annual_for_reform(
        reform_name="synthetic",
        static_group=_static_frame(),
        endpoint_group=_anchors(anchor_rows),
        fallback_records=[],
    )
    return out.set_index("year")


def test_endpoint_only_matches_single_segment_formula():
    # ratio(2026) = 90/100, ratio(2100) = 235/470 = 0.5
    out = _build({2026: 90.0, 2100: 235.0})
    year = 2063  # halfway: weight 0.5
    ratio = 0.9 + (0.5 - 0.9) * ((year - 2026) / (2100 - 2026))
    static = 100.0 + 5.0 * (year - 2026)
    assert out.loc[year, "revenue_impact"] == pytest.approx(static * ratio)
    assert (
        out.loc[year, "full_h5_result_type"]
        == "linear_interpolation_between_behavioral_endpoint_ratios"
    )


def test_interior_anchor_bends_the_ratio_path():
    # Interior anchor at 2062 with ratio 1.0 (280/280); endpoints at 0.9/0.5.
    out = _build({2026: 90.0, 2062: 280.0, 2100: 235.0})

    # The anchor year itself is exact.
    assert out.loc[2062, "revenue_impact"] == pytest.approx(280.0)
    assert (
        out.loc[2062, "full_h5_result_type"] == "exact_behavioral_endpoint_full_h5"
    )

    # A year inside the first segment uses the 2026->2062 ratio line...
    year = 2044  # halfway 2026->2062
    seg_ratio = 0.9 + (1.0 - 0.9) * ((year - 2026) / (2062 - 2026))
    static = 100.0 + 5.0 * (year - 2026)
    assert out.loc[year, "revenue_impact"] == pytest.approx(static * seg_ratio)

    # ...NOT the single-segment 2026->2100 line.
    single = 0.9 + (0.5 - 0.9) * ((year - 2026) / (2100 - 2026))
    assert out.loc[year, "revenue_impact"] != pytest.approx(static * single)

    # A year in the second segment uses the 2062->2100 ratio line.
    year = 2081  # halfway 2062->2100
    seg_ratio = 1.0 + (0.5 - 1.0) * ((year - 2062) / (2100 - 2062))
    static = 100.0 + 5.0 * (year - 2026)
    assert out.loc[year, "revenue_impact"] == pytest.approx(static * seg_ratio)


def test_interior_rows_keep_tob_additivity():
    out = _build({2026: 90.0, 2062: 280.0, 2100: 235.0})
    interior = out[
        out["full_h5_result_type"]
        == "linear_interpolation_between_behavioral_endpoint_ratios"
    ]
    residual = (
        interior["tob_total_impact"]
        - interior["tob_oasdi_impact"]
        - interior["tob_medicare_hi_impact"]
    ).abs()
    assert float(residual.max()) < 1e-9

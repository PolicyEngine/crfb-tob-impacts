from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from scripts.publish_balanced_fix_results import (
    DEFAULT_RUN_PREFIX,
    INTERPOLATED_RESULT_TYPE,
    build_balanced_fix_results,
    current_law_default_rows,
)
from src.balanced_fix import BALANCED_FIX_REFORMS


REPO = Path(__file__).resolve().parents[1]


def _current(
    reform: str, year: int, revenue_impact: float = 100.0
) -> dict[str, object]:
    return {
        "reform_name": reform,
        "year": year,
        "baseline_tax_assumption_name": "trustees",
        "baseline_tax_assumption_active": True,
        "baseline_revenue": 1000.0,
        "reform_revenue": 1000.0 + revenue_impact,
        "revenue_impact": revenue_impact,
        "baseline_tob_medicare_hi": 40.0,
        "reform_tob_medicare_hi": 50.0,
        "tob_medicare_hi_impact": 10.0,
        "baseline_tob_oasdi": 60.0,
        "reform_tob_oasdi": 90.0,
        "tob_oasdi_impact": 30.0,
        "baseline_tob_total": 100.0,
        "reform_tob_total": 140.0,
        "tob_total_impact": 40.0,
        "scoring_type": "static",
        "employer_ss_tax_revenue": 0.0,
        "employer_medicare_tax_revenue": 0.0,
        "oasdi_gain": 0.0,
        "hi_gain": 0.0,
        "oasdi_loss": 0.0,
        "hi_loss": 0.0,
        "oasdi_net_impact": 0.0,
        "hi_net_impact": 0.0,
    }


def _anchor(
    reform: str, year: int, revenue_impact: float, oasdi: float, hi: float
) -> dict[str, object]:
    """A solvent anchor row: reform_revenue - baseline_revenue == revenue_impact,
    and the solvent split sums to revenue_impact."""
    row = _current(reform, year, revenue_impact)
    row.update(
        {
            "solvent_baseline": "ss_solvent",
            "solvent_oasdi_impact": oasdi,
            "solvent_medicare_hi_impact": hi,
            "solvent_general_fund_impact": revenue_impact - oasdi - hi,
            "anchor_source_path": f"tmp/{year}.csv",
            "anchor_source_sha256": f"sha-{year}",
        }
    )
    return row


def _build(anchor_ri: dict[int, float], current_ri) -> pd.DataFrame:
    anchors = pd.DataFrame(
        [
            _anchor(reform, year, ri, oasdi=ri * 0.6, hi=ri * 0.4)
            for reform in BALANCED_FIX_REFORMS
            for year, ri in anchor_ri.items()
        ]
    )
    current_rows = [
        _current(reform, year, revenue_impact=current_ri(reform, year))
        for reform in BALANCED_FIX_REFORMS
        for year in range(2035, 2101)
    ]
    current = current_law_default_rows(pd.DataFrame(current_rows))
    return build_balanced_fix_results(anchors, current)


def test_publisher_interpolates_anchors_not_a_current_law_ratio():
    """Non-anchor years must come from a straight interpolation of the real
    solvent anchor rows, independent of the live current-law row. The old scheme
    scaled the current-law row by an interpolated solvent/current-law ratio; this
    fixture makes the current-law row spike at 2040 so the two methods diverge."""
    anchor_ri = {2035: 100.0, 2050: 130.0, 2065: 160.0, 2075: 180.0, 2100: 200.0}
    published = _build(
        anchor_ri,
        current_ri=lambda reform, year: 999.0 if year == 2040 else 100.0,
    )

    row = published[
        (published["reform_name"].eq("option1")) & (published["year"].eq(2040))
    ].iloc[0]
    # Direct interpolation of anchors 2035=100 and 2050=130 at 2040 -> 110.
    expected = 100.0 + (130.0 - 100.0) * (2040 - 2035) / (2050 - 2035)
    assert row["revenue_impact"] == pytest.approx(expected)
    # A ratio scheme would have amplified the 999 current-law spike; direct
    # interpolation ignores it entirely.
    assert row["revenue_impact"] < 200.0


def test_publisher_holds_identities_and_never_craters():
    """revenue_impact == reform_revenue - baseline_revenue and the split identity
    must hold at every interpolated year, and a current-law series that crosses
    zero between anchors (which exploded the old ratio method) must not produce a
    crater — the interpolated totals stay inside the anchor envelope."""
    anchor_ri = {2035: 300.0, 2050: 290.0, 2065: 270.0, 2075: 380.0, 2100: 890.0}
    crater_cl = {2054: 0.0004, 2055: -0.0003, 2058: 0.0002, 2060: -0.0001}
    published = _build(
        anchor_ri,
        current_ri=lambda reform, year: (
            crater_cl.get(year, 100.0) if reform == "option1" else 100.0
        ),
    )

    # Identity 1: revenue_impact reconciles with reform - baseline everywhere.
    ri_off = (
        (
            published["revenue_impact"]
            - (published["reform_revenue"] - published["baseline_revenue"])
        )
        .abs()
        .max()
    )
    assert ri_off < 1e-9

    # Identity 2: the solvent split sums to revenue_impact.
    split = (
        published["solvent_oasdi_impact"]
        + published["solvent_medicare_hi_impact"]
        + published["solvent_general_fund_impact"]
    )
    assert (split - published["revenue_impact"]).abs().max() < 1e-8

    # No crater: option1's interpolated totals over 2035-2065 stay within the
    # 270-300 anchor envelope and never collapse toward the near-zero current law.
    o1 = published[
        (published["reform_name"].eq("option1"))
        & (published["balanced_fix_result_type"].eq(INTERPOLATED_RESULT_TYPE))
        & (published["year"].between(2036, 2064))
    ]
    assert o1["revenue_impact"].between(269.0, 301.0).all()
    assert (o1["revenue_impact"].abs() > 50.0).all()


def test_balanced_fix_publisher_default_prefix_matches_public_metadata():
    metadata = json.loads(
        (
            REPO
            / "results"
            / "modal_runs_production"
            / "balanced_fix_results_metadata.json"
        ).read_text(encoding="utf-8")
    )
    assert DEFAULT_RUN_PREFIX == metadata["run_prefix"]
    # The metadata counter must track the tag the build step actually writes.
    assert metadata["interpolated_rows"] == 244
    assert metadata["exact_rows"] == 20

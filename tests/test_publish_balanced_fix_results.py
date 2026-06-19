from __future__ import annotations

import pandas as pd

from scripts.publish_balanced_fix_results import (
    build_balanced_fix_results,
    current_law_default_rows,
)
from src.balanced_fix import BALANCED_FIX_PUBLISH_ANCHOR_YEARS, BALANCED_FIX_REFORMS


def _current_row(reform: str, year: int, revenue: float = 100.0) -> dict[str, object]:
    return {
        "reform_name": reform,
        "year": year,
        "baseline_tax_assumption_name": "trustees",
        "baseline_tax_assumption_active": True,
        "baseline_revenue": 1000.0 + year,
        "reform_revenue": 1000.0 + year + revenue,
        "revenue_impact": revenue,
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


def _anchor_row(reform: str, year: int, ratio: float) -> dict[str, object]:
    row = _current_row(reform, year)
    row.update(
        {
            "baseline_revenue": row["baseline_revenue"] * ratio,
            "reform_revenue": row["reform_revenue"] * ratio,
            "revenue_impact": row["revenue_impact"] * ratio,
            "solvent_baseline": "ss_solvent",
            "solvent_oasdi_impact": 60.0 * ratio,
            "solvent_medicare_hi_impact": 40.0 * ratio,
            "solvent_general_fund_impact": 0.0,
            "anchor_source_path": f"tmp/{year}.csv",
            "anchor_source_sha256": f"sha-{year}",
        }
    )
    return row


def test_balanced_fix_publisher_interpolates_ratios_and_reconciles_split():
    current_rows = [
        _current_row(reform, year)
        for reform in BALANCED_FIX_REFORMS
        for year in range(2035, 2101)
    ]
    anchors = pd.DataFrame(
        [
            _anchor_row(reform, year, 1.0 + index * 0.1)
            for reform in BALANCED_FIX_REFORMS
            for index, year in enumerate(BALANCED_FIX_PUBLISH_ANCHOR_YEARS)
        ]
    )

    current = current_law_default_rows(pd.DataFrame(current_rows))
    published = build_balanced_fix_results(anchors, current)

    assert set(published["baseline_scenario"]) == {"ss_solvent"}
    assert (
        published.groupby("reform_name")["year"]
        .agg(["min", "max", "count"])["count"]
        .eq(66)
        .all()
    )

    exact = published[
        published["balanced_fix_result_type"].eq("exact_solvent_baseline_full_h5")
    ]
    assert set(exact["year"]) == set(BALANCED_FIX_PUBLISH_ANCHOR_YEARS)

    option1_2040 = published[
        (published["reform_name"].eq("option1")) & (published["year"].eq(2040))
    ].iloc[0]
    expected_ratio = 1.0 + (0.1 * (2040 - 2035) / (2050 - 2035))
    assert option1_2040["revenue_impact"] == 100.0 * expected_ratio

    split_total = (
        published["solvent_oasdi_impact"]
        + published["solvent_medicare_hi_impact"]
        + published["solvent_general_fund_impact"]
    )
    assert (split_total - published["revenue_impact"]).abs().max() < 1e-8

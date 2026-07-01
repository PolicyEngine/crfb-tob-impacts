"""Guard the citable headline summary (10-year and 75-year PV figures).

The dashboard computes these figures client-side; headline_summary.csv is the
server-side record the paper cites. These tests keep the committed outputs
regenerable from the checked-in inputs and pin the values that were verified
against the rendered dashboard, so silent drift in the split or discounting
logic fails here first.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

import pytest

from scripts.build_headline_summary import REFORM_LABELS, build

REPO = Path(__file__).resolve().parents[1]
SUMMARY = REPO / "dashboard" / "public" / "data" / "headline_summary.csv"
REFORMS_TS = REPO / "dashboard" / "src" / "lib" / "reforms.ts"


def committed_rows() -> list[dict[str, str]]:
    with SUMMARY.open() as file:
        return list(csv.DictReader(file))


def test_committed_summary_matches_regeneration():
    regenerated = {(str(r["baseline_scenario"]), str(r["reform"])): r for r in build()}
    committed = committed_rows()
    assert len(committed) == len(regenerated)
    for row in committed:
        rebuilt = regenerated[(row["baseline_scenario"], row["reform"])]
        for column, value in row.items():
            if column in ("baseline_scenario", "reform"):
                continue
            assert float(value) == pytest.approx(float(rebuilt[column]), abs=1e-3), (
                f"{row['reform']} {column} stale: committed {value}, "
                f"regenerated {rebuilt[column]}; rerun "
                "scripts/build_headline_summary.py"
            )


def test_components_sum_to_total():
    for row in committed_rows():
        total = float(row["pv75_total_billions"])
        parts = (
            float(row["pv75_oasdi_billions"])
            + float(row["pv75_medicare_hi_billions"])
            + float(row["pv75_general_fund_billions"])
        )
        assert total == pytest.approx(parts, abs=1e-3)


def test_dashboard_verified_values_are_pinned():
    """Values read off the rendered dashboard on 2026-07-01 after the
    effective-rate and tax93-default corrections."""
    rows = {(r["baseline_scenario"], r["reform"]): r for r in committed_rows()}
    pins = {
        ("scheduled_benefits", "option1"): ("pv75_total_billions", -10879.2),
        ("scheduled_benefits", "tax93"): ("ten_year_nominal_billions", 670.8),
        ("scheduled_benefits", "reverse_roth"): ("pv75_total_billions", -4164.2),
    }
    for key, (column, expected) in pins.items():
        assert float(rows[key][column]) == pytest.approx(expected, abs=0.5)
    tax93 = rows[("scheduled_benefits", "tax93")]
    assert float(tax93["pv75_oasdi_billions"]) == pytest.approx(1598, abs=2)
    assert float(tax93["pv75_medicare_hi_billions"]) == pytest.approx(1188, abs=2)


def test_labels_and_order_mirror_the_dashboard():
    reforms_ts = REFORMS_TS.read_text(encoding="utf-8")
    order_block = re.search(
        r"const REFORM_DISPLAY_ORDER = \[(.*?)\];", reforms_ts, re.S
    )
    assert order_block
    ts_order = re.findall(r'"([a-z0-9_]+)"', order_block.group(1))
    assert list(REFORM_LABELS) == ts_order
    for reform, label in REFORM_LABELS.items():
        assert f'shortName: "{label}"' in reforms_ts, (
            f"label for {reform} diverged from reforms.ts"
        )

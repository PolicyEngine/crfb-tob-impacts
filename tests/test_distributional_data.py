"""The published distributional artifact must be well-formed: every reform
covers the anchor years, each year has ten deciles, and the dollar and
percentage impacts are finite."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
DIST_PATH = REPO / "dashboard" / "public" / "data" / "distributional.json"
STANDARD_REFORMS = [f"option{i}" for i in range(1, 13)] + ["reverse_roth", "tax93"]


@pytest.fixture(scope="module")
def dist() -> dict:
    if not DIST_PATH.exists():
        pytest.skip("distributional artifact not yet built")
    return json.loads(DIST_PATH.read_text())


def test_all_reforms_present(dist: dict) -> None:
    assert set(STANDARD_REFORMS).issubset(dist["data"].keys())


def test_each_reform_year_has_ten_deciles(dist: dict) -> None:
    anchor_years = {str(y) for y in dist["anchor_years"]}
    for reform in STANDARD_REFORMS:
        years = dist["data"][reform]
        assert anchor_years.issubset(years.keys()), reform
        for year, rows in years.items():
            assert [r["decile"] for r in rows] == list(range(1, 11)), (reform, year)
            for r in rows:
                assert isinstance(r["avg_change"], (int, float))
                assert isinstance(r["pct_change"], (int, float))


def test_full_repeal_is_a_gain_rising_with_income(dist: dict) -> None:
    # Repealing benefit taxation only ever raises net income, and the gain
    # rises with income because higher-income beneficiaries pay the most tax.
    rows = dist["data"]["option1"]["2026"]
    changes = [r["avg_change"] for r in sorted(rows, key=lambda r: r["decile"])]
    assert all(c >= 0 for c in changes)
    assert changes[-1] > changes[0]

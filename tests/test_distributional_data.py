"""The published distributional artifact must be well-formed: every reform
covers the anchor years, each year has ten deciles, and the dollar and
percentage impacts are finite."""

from __future__ import annotations

import json
from pathlib import Path

import microdf as mdf
import pandas as pd
import pytest

from scripts.build_distributional_data import decile_impacts

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


def test_distributional_builder_does_not_fetch_policyengine_weights_directly() -> None:
    source = (REPO / "scripts" / "build_distributional_data.py").read_text(
        encoding="utf-8"
    )

    assert 'calc("household_weight"' not in source
    assert 'calculate("household_weight"' not in source
    assert "weights=group" not in source
    assert "household_weight" not in source


def test_decile_impacts_preserves_microdataframe_weights_after_merge() -> None:
    baseline = mdf.MicroDataFrame(
        {
            "household_id": [1, 2],
            "baseline_net_income": [10_000_000_000, 20_000_000_000],
            "decile": [1, 1],
        },
        weights=[1, 3],
    )
    reform = pd.DataFrame(
        {
            "household_id": [1, 2],
            "reform_net_income": [11_000_000_000, 24_000_000_000],
        }
    )

    decile_1 = decile_impacts(baseline, reform)[0]

    assert decile_1["avg_change"] == 3_250_000_000
    assert decile_1["total_change_billions"] == 13.0
    assert decile_1["pct_change"] == 18.571


def test_each_reform_year_has_ten_deciles(dist: dict) -> None:
    anchor_years = {str(y) for y in dist["anchor_years"]}
    for reform in STANDARD_REFORMS:
        years = dist["data"][reform]
        assert anchor_years.issubset(years.keys()), reform
        for year, rows in years.items():
            assert [r["decile"] for r in rows] == list(range(1, 11)), (reform, year)
            for r in rows:
                assert isinstance(r["avg_change"], (int, float))
                # pct_change is a finite number or null (suppressed where the
                # decile's aggregate baseline net income is not positive).
                assert r["pct_change"] is None or isinstance(
                    r["pct_change"], (int, float)
                )


def test_percentages_are_suppressed_not_fabricated(dist: dict) -> None:
    # Where a percent is reported it must be a sane magnitude. The old
    # negative-denominator bug produced a -63% bottom-decile outlier; deciles
    # with a non-positive baseline must be null rather than a fabricated value.
    for reform in STANDARD_REFORMS:
        for year, rows in dist["data"][reform].items():
            for r in rows:
                # Real max across all cells is ~2.5%; a 10% ceiling leaves
                # ample headroom while still catching a sign-flip regression.
                if r["pct_change"] is not None:
                    assert abs(r["pct_change"]) < 10.0, (reform, year, r)


def test_reverse_roth_is_u_shaped_in_2026(dist: dict) -> None:
    # Low earners gain (payroll-tax deduction), middle deciles lose (full
    # benefit taxation), top deciles gain again.
    rows = {r["decile"]: r["avg_change"] for r in dist["data"]["reverse_roth"]["2026"]}
    assert rows[3] < 0 < rows[10]
    assert rows[10] > rows[6]


def test_full_repeal_is_a_gain_rising_with_income(dist: dict) -> None:
    # Repealing benefit taxation only ever raises net income, and the gain
    # rises with income because higher-income beneficiaries pay the most tax.
    rows = dist["data"]["option1"]["2026"]
    changes = [r["avg_change"] for r in sorted(rows, key=lambda r: r["decile"])]
    assert all(c >= 0 for c in changes)
    assert changes[-1] > changes[0]


CERTREPRO_REFORMS = ["magi100", "tax_panel_2005"]


def test_certrepro_reforms_have_full_anchor_coverage(dist: dict) -> None:
    # magi100 and tax_panel_2005 pair certrepro reform legs with same-family
    # exported baselines; both must carry every anchor year with ten deciles.
    for reform in CERTREPRO_REFORMS:
        by_year = dist["data"][reform]
        assert len(by_year) >= 16
        for year, rows in by_year.items():
            assert len(rows) == 10, (reform, year)
            assert [r["decile"] for r in rows] == list(range(1, 11))


def test_magi100_is_a_middle_decile_loss_in_2026(dist: dict) -> None:
    # Counting 100% of benefits in the income test only ever raises tax, and
    # the burden lands on middle-income beneficiary households below the 85%
    # cap; the bottom is below the thresholds and the top is already capped.
    rows = {r["decile"]: r["avg_change"] for r in dist["data"]["magi100"]["2026"]}
    assert all(change <= 0 for change in rows.values())
    assert min(rows[4], rows[5], rows[6], rows[7]) < rows[1]
    assert min(rows[4], rows[5], rows[6], rows[7]) < rows[10]


def test_tax_panel_2005_crosses_from_loss_to_gain_in_2026(dist: dict) -> None:
    # The Panel deduction taxes benefits at lower non-benefit income than
    # current law (losses in the lower-middle deciles) but phases in at 50
    # cents per dollar instead of the 85-cent second tier (gains above).
    rows = {r["decile"]: r["avg_change"] for r in dist["data"]["tax_panel_2005"]["2026"]}
    assert rows[3] < 0 and rows[4] < 0
    assert all(rows[d] > 0 for d in (7, 8, 9, 10))

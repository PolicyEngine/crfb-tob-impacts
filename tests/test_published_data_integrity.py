"""Invariant gate on the published dashboard data.

The solvency crater (option12 2055/2060) lived in the published CSVs for days
because nothing checked that derived columns stay consistent with the raw
simulation aggregates. These tests make that class of corruption a test
failure instead of a partner-reported bug.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RESULTS = REPO / "dashboard" / "public" / "data" / "results.csv"
BALANCED_DASHBOARD = REPO / "dashboard" / "public" / "data" / "balanced_fix_results.csv"
BALANCED_MODAL = REPO / "results" / "modal_runs_production" / "balanced_fix_results.csv"
RATES = REPO / "dashboard" / "public" / "data" / "effective_interest_rates.csv"
DASHBOARD_DATA_TS = REPO / "dashboard" / "src" / "lib" / "dashboard-data.ts"
REFORMS_TS = REPO / "dashboard" / "src" / "lib" / "reforms.ts"


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open() as file:
        return list(csv.DictReader(file))


def test_revenue_impact_reconciles_with_raw_aggregates():
    """revenue_impact must equal reform_revenue - baseline_revenue at every
    exact (non-interpolated) row of both published result files."""
    for path in (RESULTS, BALANCED_DASHBOARD):
        for row in _rows(path):
            result_type = row.get("full_h5_result_type", "") or row.get(
                "balanced_fix_result_type", ""
            )
            if "interp" in result_type:
                continue
            off = float(row["revenue_impact"]) - (
                float(row["reform_revenue"]) - float(row["baseline_revenue"])
            )
            assert abs(off) < 0.01, (
                f"{path.name}: {row['reform_name']} {row['year']} "
                f"revenue_impact off by {off:+.2f}"
            )


def test_solvent_split_sums_to_revenue_impact_everywhere():
    for row in _rows(BALANCED_DASHBOARD):
        total = (
            float(row["solvent_oasdi_impact"])
            + float(row["solvent_medicare_hi_impact"])
            + float(row["solvent_general_fund_impact"])
        )
        off = total - float(row["revenue_impact"])
        assert abs(off) < 1e-4, (
            f"balanced_fix: {row['reform_name']} {row['year']} split off by {off:+.6f}"
        )


def test_balanced_fix_copies_are_identical():
    assert BALANCED_DASHBOARD.read_bytes() == BALANCED_MODAL.read_bytes(), (
        "The dashboard and modal_runs_production copies of "
        "balanced_fix_results.csv have drifted apart; regenerate both with "
        "scripts/publish_balanced_fix_results.py."
    )


def test_effective_interest_rates_cover_the_projection_window():
    rows = _rows(RATES)
    years = sorted(int(r["year"]) for r in rows)
    assert years == list(range(2026, 2101))
    for row in rows:
        for column in ("oasdi_effective_rate_pct", "hi_effective_rate_pct"):
            rate = float(row[column])
            assert 2.0 < rate < 6.0, f"{column} {row['year']} = {rate} out of range"


def test_reform_display_order_covers_every_reform():
    """A reform id missing from REFORM_DISPLAY_ORDER would silently sort first
    (indexOf -> -1); require the list to name every defined reform."""
    reforms_ts = REFORMS_TS.read_text(encoding="utf-8")
    defined = set(re.findall(r'^\s+id: "([a-z0-9_]+)"', reforms_ts, re.M))
    order_block = re.search(
        r"const REFORM_DISPLAY_ORDER = \[(.*?)\];", reforms_ts, re.S
    )
    assert order_block, "REFORM_DISPLAY_ORDER missing from reforms.ts"
    ordered = set(re.findall(r'"([a-z0-9_]+)"', order_block.group(1)))
    assert defined == ordered, (
        f"REFORM_DISPLAY_ORDER out of sync with definitions: "
        f"missing={sorted(defined - ordered)}, extra={sorted(ordered - defined)}"
    )


def test_allocation_rule_sets_mirror_python():
    """The dashboard's allocation sets must match src/trust_fund_allocation.py."""
    from src.trust_fund_allocation import load_allocation_rules

    ts = DASHBOARD_DATA_TS.read_text(encoding="utf-8")

    def ts_set(name: str) -> set[str]:
        block = re.search(rf"const {name} = new Set\(\[(.*?)\]\);", ts, re.S)
        assert block, f"{name} missing from dashboard-data.ts"
        return set(re.findall(r'"([a-z0-9_]+)"', block.group(1)))

    rules = load_allocation_rules()
    assert ts_set("allocationEligibleOptions") == rules["allocationEligibleOptions"]
    assert ts_set("baselineShareOptions") == rules["baselineShareOptions"]
    assert ts_set("netImpactOptions") == rules["netImpactOptions"]
    assert ts_set("directBranchingOptions") == rules["directBranchingOptions"]

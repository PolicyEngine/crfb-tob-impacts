"""Conform every static row to one pooled exact-anchor baseline series (M-01).

The published static panel is supposed to share a single current-law
baseline series across reforms (the full-panel publisher builds it by
pooling every exact anchor year and interpolating between them). The
post-publication splices broke that invariant in two ways the audit
flagged: magi100/tax_panel_2005 interpolated their baseline columns over
their own 18 anchors only (a $25.7B baseline spread against the legacy
panel at option6's 2033 anchor), and new exact anchors (option6's
rescored 2029-2033, the option12/option5 2062 completion anchor) updated
some reforms' baselines but not the interpolated rows around them.

This script rebuilds the pooled series from the CURRENT exact rows and
conforms every static row to it:

- pooled anchor value per year/column = the value carried by the most
  exact rows at that year (families agree to $1,368 at worst, asserted
  <= $2M);
- non-anchor years interpolate the pooled series piecewise-linearly;
- every static row's baseline_* columns are set to the series and its
  reform_* level columns re-derived as baseline + impact. Impact columns
  are untouched. Reform-level columns therefore equal the shared pooled
  baseline plus the row's (linear) impact rather than lying on a
  straight line between the reform's own anchors; the baseline series
  itself is piecewise-linear over all pooled anchors.

Usage: .venv/bin/python scripts/fix_pooled_baseline_series.py
"""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TARGETS = (REPO / "results.csv", REPO / "dashboard" / "public" / "data" / "results.csv")
BASELINE_AGGREGATES = REPO / "dashboard" / "public" / "data" / "baseline_aggregates.csv"
RAW_STATIC_CELLS = REPO / "results" / "modal_runs_production" / "static_cells.csv"

BASELINE_COLUMNS = (
    "baseline_revenue",
    "baseline_tob_medicare_hi",
    "baseline_tob_oasdi",
    "baseline_tob_total",
)
REFORM_LEVEL_COLUMNS = {
    "reform_revenue": ("baseline_revenue", "revenue_impact"),
    "reform_tob_medicare_hi": ("baseline_tob_medicare_hi", "tob_medicare_hi_impact"),
    "reform_tob_oasdi": ("baseline_tob_oasdi", "tob_oasdi_impact"),
    "reform_tob_total": ("baseline_tob_total", "tob_total_impact"),
}
MAX_ANCHOR_SPREAD_BILLIONS = 2e-3


def _raw_baseline_series() -> dict[str, dict[int, float]]:
    """Per-year baseline values recorded in the raw production aggregate.

    Where the June full-H5 runs measured a year's baseline directly, the
    pooled series keeps that raw measurement — the release invariant pins
    published exact baselines to the raw artifact. Rescored anchors on
    byte-identical datasets reproduce these to ~$3k; the raw value wins
    for continuity.
    """
    import pandas as pd

    raw = pd.read_csv(RAW_STATIC_CELLS)
    series: dict[str, dict[int, float]] = {c: {} for c in BASELINE_COLUMNS}
    for year, group in raw.groupby("year"):
        for column in BASELINE_COLUMNS:
            if column not in group.columns:
                continue
            values = pd.to_numeric(group[column], errors="coerce").dropna() / 1e9
            if values.empty:
                continue
            if values.max() - values.min() > MAX_ANCHOR_SPREAD_BILLIONS:
                raise SystemExit(
                    f"raw {column} spread at {year}: "
                    f"{values.max() - values.min():.6f}B"
                )
            series[column][int(year)] = float(values.iloc[0])
    return series


def pooled_series(rows: list[dict]) -> dict[str, dict[int, float]]:
    exact = [
        r
        for r in rows
        if r["scoring_type"] == "static"
        and r["full_h5_result_type"] == "exact_full_h5"
    ]
    raw_series = _raw_baseline_series()
    series: dict[str, dict[int, float]] = {c: {} for c in BASELINE_COLUMNS}
    by_year: dict[int, list[dict]] = {}
    for r in exact:
        by_year.setdefault(int(r["year"]), []).append(r)
    for year, group in sorted(by_year.items()):
        for column in BASELINE_COLUMNS:
            values = [float(g[column]) for g in group if g.get(column) not in ("", None)]
            if not values:
                continue
            raw_value = raw_series[column].get(year)
            candidates = values + ([raw_value] if raw_value is not None else [])
            spread = max(candidates) - min(candidates)
            if spread > MAX_ANCHOR_SPREAD_BILLIONS:
                raise SystemExit(
                    f"{column} spread at {year} is {spread:.6f}B across "
                    f"{len(candidates)} exact/raw values; refusing to pool"
                )
            if raw_value is not None:
                series[column][year] = raw_value
            else:
                # Majority value: certified families agree to ~$1k; where
                # they differ, keep the value carried by the most rows.
                counts = Counter(values)
                series[column][year] = counts.most_common(1)[0][0]
    return series


def interpolate(series: dict[int, float], year: int) -> float:
    if year in series:
        return series[year]
    years = sorted(series)
    left = max(y for y in years if y < year)
    right = min(y for y in years if y > year)
    weight = (year - left) / (right - left)
    return series[left] + weight * (series[right] - series[left])


def main() -> int:
    for target in TARGETS:
        with target.open() as file:
            reader = csv.DictReader(file)
            columns = reader.fieldnames or []
            rows = list(reader)
        series = pooled_series(rows)
        anchor_years = sorted(series[BASELINE_COLUMNS[0]])
        print(f"{target.name}: pooled anchors {anchor_years}")

        worst: tuple[float, str, str] = (0.0, "", "")
        changed = 0
        for row in rows:
            if row["scoring_type"] != "static":
                continue
            year = int(row["year"])
            row_changed = False
            for column in BASELINE_COLUMNS:
                if row.get(column) in ("", None):
                    continue
                new = interpolate(series[column], year)
                old = float(row[column])
                if abs(new - old) > 5e-11:
                    delta = abs(new - old)
                    if delta > worst[0]:
                        worst = (delta, f"{row['reform_name']} {year}", column)
                    row[column] = f"{new:.10f}"
                    row_changed = True
            for reform_column, (baseline_column, impact_column) in (
                REFORM_LEVEL_COLUMNS.items()
            ):
                if (
                    row.get(reform_column) in ("", None)
                    or row.get(baseline_column) in ("", None)
                    or row.get(impact_column) in ("", None)
                ):
                    continue
                level = float(row[baseline_column]) + float(row[impact_column])
                if abs(level - float(row[reform_column])) > 5e-11:
                    row[reform_column] = f"{level:.10f}"
                    row_changed = True
            changed += row_changed

        print(
            f"{target.name}: {changed} static rows conformed; worst baseline "
            f"delta {worst[0]:.6f}B at {worst[1]} {worst[2]}"
        )
        with target.open("w", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)

        if target == TARGETS[0]:
            revenue_series = series["baseline_revenue"]

    # The baseline diagnostics artifact publishes the same current-law
    # income-tax series; conform its non-anchor years to the pooled series
    # so the release invariant (option1 baseline == diagnostics series at
    # every year) keeps holding.
    with BASELINE_AGGREGATES.open() as file:
        reader = csv.DictReader(file)
        agg_columns = reader.fieldnames or []
        agg_rows = list(reader)
    agg_changed = 0
    for row in agg_rows:
        year = int(row["year"])
        new = interpolate(revenue_series, year)
        if abs(new - float(row["federal_income_tax"])) > 5e-10:
            row["federal_income_tax"] = f"{new:.9f}"
            if row.get("gdp") not in ("", None):
                row["federal_income_tax_pct_gdp"] = (
                    f"{new / float(row['gdp']) * 100:.9f}"
                )
            agg_changed += 1
    print(f"{BASELINE_AGGREGATES.name}: {agg_changed} years conformed")
    with BASELINE_AGGREGATES.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=agg_columns)
        writer.writeheader()
        writer.writerows(agg_rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

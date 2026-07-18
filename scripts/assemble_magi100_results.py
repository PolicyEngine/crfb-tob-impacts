"""Append the certified magi100 (full MAGI inclusion) rows to the results panel.

Consumes the aggregated anchor cells produced by the certified scoring run
(``tmp/magi100_rows_dollars.json`` — dollar aggregates computed against the
published panel's own baselines by the local full-H5 aggregation), scales to
billions, interpolates non-anchor years linearly between anchors following the
panel convention, and writes the magi100 rows into both tracked copies of
``results.csv`` (repo root and ``dashboard/public/data``). Idempotent: existing
magi100 rows are replaced.

Requires all 18 production anchor years; refuses partial assembly so the
published panel never carries an incomplete reform.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CELLS = REPO / "tmp" / "magi100_rows_dollars.json"
TARGETS = (REPO / "results.csv", REPO / "dashboard" / "public" / "data" / "results.csv")
ANCHOR_YEARS = (2026, 2028, 2029, 2030, *range(2035, 2101, 5))
RUN_PREFIX = "magi100_certrepro_20260706"

DOLLAR_COLUMNS = (
    "baseline_revenue",
    "reform_revenue",
    "revenue_impact",
    "baseline_tob_medicare_hi",
    "reform_tob_medicare_hi",
    "tob_medicare_hi_impact",
    "baseline_tob_oasdi",
    "reform_tob_oasdi",
    "tob_oasdi_impact",
    "baseline_tob_total",
    "reform_tob_total",
    "tob_total_impact",
    "employer_ss_tax_revenue",
    "employer_medicare_tax_revenue",
    "oasdi_gain",
    "hi_gain",
    "oasdi_loss",
    "hi_loss",
    "oasdi_net_impact",
    "hi_net_impact",
)


def load_anchor_rows() -> dict[int, dict[str, object]]:
    cells = json.loads(CELLS.read_text())
    rows: dict[int, dict[str, object]] = {}
    for cell in cells:
        year = int(cell["year"])
        row = dict(cell)
        for column in DOLLAR_COLUMNS:
            row[column] = float(row[column]) / 1e9
        lineage = json.loads((REPO / "tmp" / "magi100_lineage.json").read_text())
        cell_lineage = lineage[str(year)]
        row.update(
            {
                "reform_name": "magi100",
                "scoring_type": "static",
                "source": "exact_full_h5",
                "full_h5_result_type": "exact_full_h5",
                "run_prefix": RUN_PREFIX,
                "scenario_h5_uri": cell_lineage["scenario_h5_uri"],
                "metadata_uri": cell_lineage["metadata_uri"],
                "complete_uri": "",
                "output_h5_sha256": cell_lineage["output_h5_sha256"],
                "baseline_source": "v2pop_tr2026_baseline_h5",
            }
        )
        rows[year] = row
    missing = [y for y in ANCHOR_YEARS if y not in rows]
    if missing:
        raise RuntimeError(f"magi100 anchors missing: {missing}; refusing assembly.")
    return rows


def interpolated(anchors: dict[int, dict[str, object]]) -> list[dict[str, object]]:
    years = sorted(anchors)
    out: list[dict[str, object]] = []
    for left, right in zip(years, years[1:]):
        for year in range(left + 1, right):
            weight = (year - left) / (right - left)
            row = dict(anchors[left])
            for column in DOLLAR_COLUMNS:
                lo = float(anchors[left][column])
                hi = float(anchors[right][column])
                row[column] = lo + weight * (hi - lo)
            row.update(
                {
                    "year": year,
                    "source": "linear_interpolation_between_full_h5_years",
                    "full_h5_result_type": (
                        "linear_interpolation_between_full_h5_years"
                    ),
                    "run_prefix": "",
                    "baseline_source": "",
                }
            )
            out.append(row)
    return out


def main() -> int:
    anchors = load_anchor_rows()
    new_rows = list(anchors.values()) + interpolated(anchors)
    for target in TARGETS:
        with target.open() as file:
            reader = csv.DictReader(file)
            columns = reader.fieldnames or []
            kept = [row for row in reader if row["reform_name"] != "magi100"]
        formatted = []
        for row in sorted(new_rows, key=lambda r: int(r["year"])):
            formatted.append(
                {
                    column: (
                        f"{row[column]:.10f}"
                        if column in DOLLAR_COLUMNS
                        else str(row.get(column, ""))
                    )
                    for column in columns
                }
            )
        with target.open("w", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=columns)
            writer.writeheader()
            writer.writerows(kept + formatted)
        print(f"wrote {len(formatted)} magi100 rows into {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

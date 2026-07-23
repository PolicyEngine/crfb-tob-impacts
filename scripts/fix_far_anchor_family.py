"""Rescore-splice: move magi100 and tax_panel_2005 far anchors to no-clone.

The certified-reproduction worktree that scored both reforms predates the
donor-clone deletion, so its 2075-2100 datasets carry 32,000 cloned
households (DONOR_CLONE_START_YEAR = 2075) while the published panel's far
anchors use the no-clone family — producing the 2070->2075 step CRFB
spotted. This script rebuilds each reform's 75-year rows by keeping the
existing exact anchors through 2070 and replacing 2075-2100 with cells
scored on the published no-clone datasets (run prefix
``noclone_farfix_20260722``), paired with the published rows' own
baselines (same family; the option2@2075 sentinel proves alignment),
then re-interpolates intermediate years. Refuses partial replacement.

Usage: .venv/bin/python scripts/fix_far_anchor_family.py
"""

from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
RUN_PREFIX = "noclone_farfix_20260722"
CELL_ROOT = REPO / "tmp" / "full_h5_noclone_farfix" / RUN_PREFIX / "reform_full_h5"
TARGETS = (REPO / "results.csv", REPO / "dashboard" / "public" / "data" / "results.csv")
REFORMS = ("magi100", "tax_panel_2005")
FAR_YEARS = (2075, 2080, 2085, 2090, 2095, 2100)

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


def _agg():
    spec = importlib.util.spec_from_file_location(
        "agg",
        Path.home()
        / "PolicyEngine/crfb-cert/scripts/aggregate_reform_full_h5_results.py",
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["agg"] = module
    spec.loader.exec_module(module)
    return module


def published_baseline(rows: list[dict], year: int):
    agg = sys.modules["agg"]
    row = next(
        r for r in rows if int(r["year"]) == year and r["scoring_type"] == "static"
    )
    return agg.BaselineResult(
        revenue=float(row["baseline_revenue"]) * 1e9,
        tob_medicare_hi=float(row["baseline_tob_medicare_hi"]) * 1e9,
        tob_oasdi=float(row["baseline_tob_oasdi"]) * 1e9,
        tob_total=float(row["baseline_tob_total"]) * 1e9,
        social_security=0.0,
        taxable_payroll=0.0,
        tax_assumption_name=str(row["baseline_tax_assumption_name"]),
        tax_assumption_active=row["baseline_tax_assumption_active"]
        in ("True", "true", "1"),
    )


def far_anchor_row(agg, all_rows: list[dict], reform: str, year: int) -> dict:
    scenario = CELL_ROOT / f"year={year}" / f"reform={reform}" / "scenario.h5"
    metadata_path = scenario.parent / "metadata.json"
    if not scenario.exists() or not metadata_path.exists():
        raise RuntimeError(f"missing noclone cell {reform} {year}; refusing splice")
    metadata = json.loads(metadata_path.read_text())
    totals = agg._aggregate_full_output_h5(scenario)
    row = agg.build_reform_result_from_aggregates(
        reform_id=reform,
        year=year,
        baseline=published_baseline(all_rows, year),
        reform_totals=totals,
        employer_net_reforms=agg.MODAL_EMPLOYER_NET_REFORMS,
        default_net_impact_mode="direct",
        scoring_type="static",
    )
    scaled = {column: row[column] / 1e9 for column in DOLLAR_COLUMNS}
    scaled.update(
        {
            "year": year,
            "reform_name": reform,
            "scoring_type": "static",
            "source": "exact_full_h5",
            "full_h5_result_type": "exact_full_h5",
            "run_prefix": RUN_PREFIX,
            "scenario_h5_uri": (
                f"r2://axiom-corpus/crfb/reform_full_h5/{RUN_PREFIX}"
                f"/reform_full_h5/year={year}/reform={reform}/scenario.h5"
            ),
            "metadata_uri": (
                f"r2://axiom-corpus/crfb/reform_full_h5/{RUN_PREFIX}"
                f"/reform_full_h5/year={year}/reform={reform}/metadata.json"
            ),
            "complete_uri": "",
            "output_h5_sha256": metadata["output_h5_sha256"],
            "baseline_source": "v2pop_tr2026_baseline_h5",
            "baseline_tax_assumption_name": metadata["tax_assumption"]["name"],
            "baseline_tax_assumption_active": str(metadata["tax_assumption"]["active"]),
        }
    )
    return scaled


def interpolate(anchors: dict[int, dict]) -> list[dict]:
    years = sorted(anchors)
    out: list[dict] = []
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
                    "scenario_h5_uri": "",
                    "metadata_uri": "",
                    "output_h5_sha256": "",
                }
            )
            out.append(row)
    return out


def main() -> int:
    agg = _agg()
    for target in TARGETS:
        with target.open() as file:
            reader = csv.DictReader(file)
            columns = reader.fieldnames or []
            rows = list(reader)

        kept = [
            r
            for r in rows
            if not (r["reform_name"] in REFORMS and r["scoring_type"] == "static")
        ]
        for reform in REFORMS:
            existing_exact = {
                int(r["year"]): r
                for r in rows
                if r["reform_name"] == reform
                and r["scoring_type"] == "static"
                and r["full_h5_result_type"] == "exact_full_h5"
                and int(r["year"]) < 2075
            }
            if not existing_exact or max(existing_exact) != 2070:
                raise RuntimeError(
                    f"{reform}: expected exact anchors through 2070, got "
                    f"{sorted(existing_exact)}"
                )
            anchors: dict[int, dict] = dict(existing_exact)
            for year in FAR_YEARS:
                anchors[year] = far_anchor_row(agg, rows, reform, year)
            rebuilt = list(anchors.values()) + interpolate(anchors)
            for row in sorted(rebuilt, key=lambda r: int(r["year"])):
                kept.append(
                    {
                        column: (
                            f"{float(row[column]):.10f}"
                            if column in DOLLAR_COLUMNS
                            else str(row.get(column, ""))
                        )
                        for column in columns
                    }
                )
            new_2075 = float(anchors[2075]["revenue_impact"])
            old_2075 = next(
                float(r["revenue_impact"])
                for r in rows
                if r["reform_name"] == reform
                and r["scoring_type"] == "static"
                and int(r["year"]) == 2075
            )
            print(
                f"{reform} 2075 anchor: {old_2075:+.2f}B (cloned) -> "
                f"{new_2075:+.2f}B (no-clone)"
            )
        with target.open("w", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=columns)
            writer.writeheader()
            writer.writerows(kept)
        print(f"wrote {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

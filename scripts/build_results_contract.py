"""Emit the canonical results contract: every published number with lineage.

One JSON artifact carries the full static panel (exact anchors and
interpolated display rows) where each value chains back to its origins:
the populace base release, the calibrated baseline year H5 (by SHA-256),
the Modal reform run and scenario H5 (by SHA-256), and the Trustees
targets expressed in populace Target grammar (name / entity / measure /
aggregation / period / value / source).

Usage:
    uv run python scripts/build_results_contract.py \
        --display results/all_static_results_full_h5_v2pop_panel_display_20260612.csv \
        --output dashboard/public/data/results_contract.json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.tob_baseline import file_sha256  # noqa: E402

BASE_DATASET = {
    "name": "populace-us-2024-9f1260b-20260611",
    "huggingface_repo": "policyengine/populace-us",
}
DEFAULT_BASELINE_MANIFEST = (
    REPO
    / "docs"
    / "current"
    / "manifests"
    / "baseline-dataset-manifest-v2pop-noclone.json"
)
DEFAULT_DISPLAY = (
    REPO / "results" / "all_static_results_full_h5_v2pop_panel_display_20260612.csv"
)
DEFAULT_LIVE_STATUS = REPO / "dashboard" / "public" / "data" / "live_reform_status.csv"
DEFAULT_OUTPUT = REPO / "dashboard" / "public" / "data" / "results_contract.json"
TR2026_AUX = REPO / "data" / "social_security_aux_tr2026.csv"

TARGET_SPECS = (
    (
        "oasdi_cost",
        "oasdi_cost_in_billion_nominal_usd",
        "social_security",
        "2026 Trustees Report IV.B1 cost rate x VI.G1 taxable payroll, intermediate assumptions",
    ),
    (
        "ssa_taxable_payroll",
        "taxable_payroll_in_billion_nominal_usd",
        "taxable_earnings_for_social_security",
        "2026 Trustees Report VI.G1, intermediate assumptions",
    ),
    (
        "oasdi_tob_revenue",
        "oasdi_tob_billions_nominal_usd",
        "tob_revenue_oasdi",
        "2026 Trustees Report IV.B2 income rate share x VI.G1 payroll",
    ),
    (
        "hi_tob_revenue",
        "hi_tob_billions_nominal_usd",
        "tob_revenue_medicare_hi",
        "CMS 2026 Medicare Trustees expanded tables, annual through 2100",
    ),
)


def targets_in_populace_grammar(anchor_years: list[int]) -> list[dict]:
    aux = pd.read_csv(TR2026_AUX).set_index("year")
    targets: list[dict] = []
    for year in anchor_years:
        if year not in aux.index:
            continue
        row = aux.loc[year]
        for name, column, measure, source in TARGET_SPECS:
            value = row.get(column)
            if pd.isna(value):
                continue
            targets.append(
                {
                    "name": f"{name}_{year}",
                    "entity": "household",
                    "measure": measure,
                    "aggregation": "sum",
                    "period": int(year),
                    "value": float(value) * 1e9,
                    "source": source,
                }
            )
    return targets


def build_contract(
    display_path: Path,
    baseline_manifest_path: Path,
    live_status_path: Path,
) -> dict:
    display = pd.read_csv(display_path)
    manifest = json.loads(baseline_manifest_path.read_text())
    year_records = manifest.get("years") or manifest.get("datasets") or {}
    if isinstance(year_records, list):
        year_records = {str(r["year"]): r for r in year_records}
    year_sha = {
        int(y): r["h5_sha256"] for y, r in year_records.items() if r.get("h5_sha256")
    }

    status = pd.read_csv(live_status_path)
    cell_sha: dict[tuple[str, int], dict] = {}
    for _, row in status.iterrows():
        key = (str(row["reform_name"]), int(row["year"]))
        cell_sha[key] = {
            "run_prefix": row.get("run_prefix") or None,
            "scenario_h5_sha256": row.get("output_h5_sha256") or None,
        }

    anchor_years = sorted(
        int(y)
        for y in display.loc[
            display["full_h5_result_type"] == "exact_full_h5", "year"
        ]
        .astype(int)
        .unique()
    )

    results = []
    for _, row in display.iterrows():
        year = int(row["year"])
        reform = str(row["reform_name"])
        exact = row["full_h5_result_type"] == "exact_full_h5"
        nearest_sha_year = (
            year if year in year_sha else min(year_sha, key=lambda y: abs(y - year))
        )
        lineage: dict = {
            "baseline_year_h5_sha256": year_sha[nearest_sha_year],
        }
        if exact:
            cell = cell_sha.get((reform, year), {})
            lineage["run_prefix"] = cell.get("run_prefix")
            sha = cell.get("scenario_h5_sha256")
            lineage["scenario_h5_sha256"] = (
                sha if isinstance(sha, str) and sha else None
            )
            lineage["interpolated_between"] = None
        else:
            below = max((y for y in anchor_years if y < year), default=None)
            above = min((y for y in anchor_years if y > year), default=None)
            lineage["run_prefix"] = None
            lineage["scenario_h5_sha256"] = None
            lineage["interpolated_between"] = [
                y for y in (below, above) if y is not None
            ]
        results.append(
            {
                "reform": reform,
                "year": year,
                "scoring_type": str(row.get("scoring_type", "static")),
                "result_type": str(row["full_h5_result_type"]),
                "revenue_impact_billions": float(row["revenue_impact"]),
                "tob_oasdi_impact_billions": _maybe(row, "tob_oasdi_impact"),
                "tob_medicare_hi_impact_billions": _maybe(
                    row, "tob_medicare_hi_impact"
                ),
                "baseline_revenue_billions": _maybe(row, "baseline_revenue"),
                "lineage": lineage,
            }
        )

    run_prefixes = sorted(
        {r["lineage"]["run_prefix"] for r in results if r["lineage"].get("run_prefix")}
    )
    return {
        "schema": "crfb_results_contract/v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "lineage": {
            "base_dataset": BASE_DATASET,
            "baseline_build": {
                "run_id": str(manifest.get("run_id")),
                "manifest_path": str(baseline_manifest_path.relative_to(REPO)),
                "manifest_sha256": file_sha256(baseline_manifest_path),
                "year_h5_sha256": {str(y): s for y, s in sorted(year_sha.items())},
            },
            "targets": targets_in_populace_grammar(anchor_years),
            "reform_runs": [
                {
                    "run_prefix": prefix,
                    "scoring_type": "static",
                    "cell_count": int(
                        sum(
                            1
                            for r in results
                            if r["lineage"].get("run_prefix") == prefix
                        )
                    ),
                }
                for prefix in run_prefixes
            ],
        },
        "results": results,
    }


def _maybe(row: pd.Series, column: str) -> float | None:
    value = row.get(column)
    if value is None or pd.isna(value):
        return None
    return float(value)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--display", type=Path, default=DEFAULT_DISPLAY)
    parser.add_argument(
        "--baseline-manifest", type=Path, default=DEFAULT_BASELINE_MANIFEST
    )
    parser.add_argument("--live-status", type=Path, default=DEFAULT_LIVE_STATUS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    contract = build_contract(args.display, args.baseline_manifest, args.live_status)

    import jsonschema

    schema = json.loads((REPO / "contracts" / "results.schema.json").read_text())
    jsonschema.validate(contract, schema)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(contract, indent=1) + "\n")
    exact = sum(1 for r in contract["results"] if r["result_type"] == "exact_full_h5")
    print(
        f"wrote {args.output}: {len(contract['results'])} rows "
        f"({exact} exact, {len(contract['results']) - exact} interpolated), "
        f"{len(contract['lineage']['targets'])} targets, schema valid"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

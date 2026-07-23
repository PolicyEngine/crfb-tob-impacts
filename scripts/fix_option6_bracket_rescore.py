"""Rescore option6 where its bracket coefficient exceeded statute (M-06).

The option6 phase-down schedule wrote its descending values to all three
``rate.additional`` parameters, including ``bracket`` — the coefficient on
the 50-85% tier that is 0.50 under current law (IRC section 86(a)(2)(A)(ii))
and is not part of the 85% family. In 2029-2034 the schedule's values exceed
0.50 (0.80 down to 0.55), so scored cells taxed the second tier above
statute; from 2035 (0.50) the cap binds nothing and published cells are
correct. The dict builders now cap the bracket at 0.50; the four affected
exact anchors (2029, 2030, 2032, 2033) are rescored on
certified-reproduction datasets, run prefix ``option6_bracketfix_20260723``.

Gates before splicing (dataset shas are already validated fail-closed by
the cell worker against the certrepro manifests):
  G2  family bridge — option6 scored with the OLD (uncapped) dict on the
      certrepro 2029 and 2032 datasets reproduces the published certinfill
      values within tolerance, so the dataset-family swap cannot
      masquerade as (or hide inside) the bracket fix;
  G3  the fixed impacts are strictly below the published (uncapped) values
      at every rescored anchor - capping a tax rate must lower revenue.

Usage (repo venv):
  .venv/bin/python scripts/fix_option6_bracket_rescore.py gate
  .venv/bin/python scripts/fix_option6_bracket_rescore.py splice
"""

from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CERT = Path.home() / "PolicyEngine/crfb-cert"
RUN_PREFIX = "option6_bracketfix_20260723"
BRIDGE_PREFIX = "option6_bridge_olddict_20260723"
CELL_ROOT = REPO / "tmp" / "full_h5_option6fix" / RUN_PREFIX / "reform_full_h5"
BRIDGE_ROOT = REPO / "tmp" / "full_h5_option6fix" / BRIDGE_PREFIX / "reform_full_h5"
BASELINE_CACHE = REPO / "tmp" / "magi100_certrepro_baselines.json"
BASELINE_3233_CACHE = REPO / "tmp" / "anchor2032_2033_baselines.json"
TARGETS = (REPO / "results.csv", REPO / "dashboard" / "public" / "data" / "results.csv")
REFORM = "option6"
RESCORED_YEARS = (2029, 2030, 2032, 2033)
INTERP_SEGMENTS = ((2030, 2032), (2033, 2035))
PUBLISHED = {2029: 90.883933, 2030: 112.726998, 2032: 160.629735, 2033: 177.506201}
BRIDGE_YEARS = (2029, 2032)
BRIDGE_TOLERANCE_B = 0.010

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
        "agg", CERT / "scripts/aggregate_reform_full_h5_results.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["agg"] = module
    spec.loader.exec_module(module)
    return module


def _baseline(agg, year: int):
    if year in (2029, 2030):
        data = json.loads(BASELINE_CACHE.read_text())[str(year)]
    else:
        data = json.loads(BASELINE_3233_CACHE.read_text())[str(year)]
    return agg.BaselineResult(**data)


def _cell_row(agg, root: Path, year: int, prefix: str) -> dict:
    scenario = root / f"year={year}" / f"reform={REFORM}" / "scenario.h5"
    metadata_path = scenario.parent / "metadata.json"
    if not scenario.exists() or not metadata_path.exists():
        raise RuntimeError(f"missing cell {prefix} {year}; refusing")
    metadata = json.loads(metadata_path.read_text())
    baseline = _baseline(agg, year)
    row = agg.build_reform_result_from_aggregates(
        reform_id=REFORM,
        year=year,
        baseline=baseline,
        reform_totals=agg._aggregate_full_output_h5(scenario),
        employer_net_reforms=agg.MODAL_EMPLOYER_NET_REFORMS,
        default_net_impact_mode="direct",
        scoring_type="static",
    )
    scaled = {column: row[column] / 1e9 for column in DOLLAR_COLUMNS}
    scaled.update(
        {
            "year": year,
            "reform_name": REFORM,
            "scoring_type": "static",
            "source": "exact_full_h5",
            "full_h5_result_type": "exact_full_h5",
            "run_prefix": prefix,
            "scenario_h5_uri": (
                f"r2://axiom-corpus/crfb/reform_full_h5/{prefix}"
                f"/reform_full_h5/year={year}/reform={REFORM}/scenario.h5"
            ),
            "metadata_uri": (
                f"r2://axiom-corpus/crfb/reform_full_h5/{prefix}"
                f"/reform_full_h5/year={year}/reform={REFORM}/metadata.json"
            ),
            "complete_uri": "",
            "output_h5_sha256": metadata["output_h5_sha256"],
            "baseline_source": "certrepro_same_dataset_baseline",
            "baseline_tax_assumption_name": metadata["tax_assumption"]["name"],
            "baseline_tax_assumption_active": str(metadata["tax_assumption"]["active"]),
        }
    )
    return scaled


def run_gate(agg=None) -> dict[int, dict]:
    agg = agg or _agg()
    failures: list[str] = []

    for year in BRIDGE_YEARS:
        bridge_path = BRIDGE_ROOT / f"year={year}" / f"reform={REFORM}"
        if not (bridge_path / "metadata.json").exists():
            print(f"[G2] bridge {year}: cell not yet run — SKIPPED (required)")
            failures.append(f"G2 {year} missing")
            continue
        bridge = _cell_row(agg, BRIDGE_ROOT, year, BRIDGE_PREFIX)
        drift = bridge["revenue_impact"] - PUBLISHED[year]
        ok = abs(drift) <= BRIDGE_TOLERANCE_B
        print(
            f"[G2] bridge old-dict {year}: {bridge['revenue_impact']:+.6f}B vs "
            f"published {PUBLISHED[year]:+.6f}B (drift {drift * 1000:+.3f}M, "
            f"{'OK' if ok else 'FAIL'})"
        )
        if not ok:
            failures.append(f"G2 {year}")

    rows: dict[int, dict] = {}
    for year in RESCORED_YEARS:
        rows[year] = _cell_row(agg, CELL_ROOT, year, RUN_PREFIX)
        drop = rows[year]["revenue_impact"] - PUBLISHED[year]
        ok = drop < 0
        print(
            f"[G3] fixed {year}: {rows[year]['revenue_impact']:+.6f}B vs published "
            f"{PUBLISHED[year]:+.6f}B (bracket-cap effect {drop:+.4f}B, "
            f"{'OK' if ok else 'FAIL: fix should reduce revenue'})"
        )
        if not ok:
            failures.append(f"G3 {year}")

    if failures:
        raise SystemExit(f"GATE FAILURES: {failures}")
    print("[gate] ALL GATES PASS")
    return rows


def splice() -> None:
    agg = _agg()
    new_rows = run_gate(agg)
    for target in TARGETS:
        with target.open() as file:
            reader = csv.DictReader(file)
            columns = reader.fieldnames or []
            rows = list(reader)

        block = {
            int(r["year"]): r
            for r in rows
            if r["reform_name"] == REFORM and r["scoring_type"] == "static"
        }
        for boundary in (2028, 2035):
            if block[boundary]["full_h5_result_type"] != "exact_full_h5":
                raise RuntimeError(f"{REFORM} {boundary} is not an exact anchor")

        replacements: dict[int, dict] = {
            year: dict(new_rows[year]) for year in RESCORED_YEARS
        }
        anchors: dict[int, dict] = {
            2028: {c: float(block[2028][c]) for c in DOLLAR_COLUMNS},
            2035: {c: float(block[2035][c]) for c in DOLLAR_COLUMNS},
            **{year: new_rows[year] for year in RESCORED_YEARS},
        }
        for left, right in INTERP_SEGMENTS:
            for year in range(left + 1, right):
                weight = (year - left) / (right - left)
                interp = {
                    c: float(anchors[left][c])
                    + weight * (float(anchors[right][c]) - float(anchors[left][c]))
                    for c in DOLLAR_COLUMNS
                }
                interp.update(
                    {
                        "year": year,
                        "reform_name": REFORM,
                        "scoring_type": "static",
                        "source": "linear_interpolation_between_full_h5_years",
                        "full_h5_result_type": (
                            "linear_interpolation_between_full_h5_years"
                        ),
                        "run_prefix": "",
                        "baseline_source": "",
                        "scenario_h5_uri": "",
                        "metadata_uri": "",
                        "complete_uri": "",
                        "output_h5_sha256": "",
                    }
                )
                replacements[year] = interp

        for row in rows:
            if (
                row["reform_name"] == REFORM
                and row["scoring_type"] == "static"
                and int(row["year"]) in replacements
            ):
                new = replacements[int(row["year"])]
                old_impact = float(row["revenue_impact"])
                for column in columns:
                    if column in DOLLAR_COLUMNS:
                        row[column] = f"{float(new[column]):.10f}"
                    elif column in new:
                        row[column] = str(new[column])
                print(
                    f"{REFORM} {row['year']}: {old_impact:+.4f}B -> "
                    f"{float(row['revenue_impact']):+.4f}B "
                    f"({row['full_h5_result_type']})"
                )
        with target.open("w", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)
        print(f"wrote {target}")


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode == "gate":
        run_gate()
    elif mode == "splice":
        splice()
    else:
        raise SystemExit("usage: fix_option6_bracket_rescore.py gate|splice")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

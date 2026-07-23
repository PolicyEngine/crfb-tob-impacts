"""Add an exact 2062 anchor for option12 and option5 (audit finding H-02).

Option12's benefit-taxation phase-out completes in 2062, reaching the same
operative tax settings as option5, but the published anchor grid (…, 2060,
2065, …) interpolated straight across the kink: the displayed 2062 gap
between the two reforms was $19.5B and only closed at the 2065 anchor.

Fix: score option12, option5, and an option1 gate cell at 2062 on a fresh
certified-reproduction dataset (`projected_datasets_certrepro/2062.h5`,
calibrated exactly to the OACT TR2026 TOB targets: OASDI $415.3305B +
HI $347.5620B = $762.8925B), run prefix ``anchor2062_20260723``, then
replace the interpolated 2061-2064 rows for the two reforms with the exact
2062 anchor and re-interpolations against their 2060/2065 parents. All
other rows pass through byte-identical (in-place row replacement, original
order preserved).

Gates before splicing:
  G1  computed certrepro 2062 baseline reproduces the OACT TOB pin;
  G2  option1@2062 == -(baseline TOB total) -- the published panel's
      option1 rows equal -baseline_tob_total exactly at every anchor;
  G3  option12@2062 == option5@2062 (identical operative settings).

Usage (repo venv, cwd = crfb-tob-impacts):
  .venv/bin/python scripts/fix_option12_2062_anchor.py baseline
  .venv/bin/python scripts/fix_option12_2062_anchor.py gate
  .venv/bin/python scripts/fix_option12_2062_anchor.py splice
"""

from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CERT = Path.home() / "PolicyEngine/crfb-cert"
RUN_PREFIX = "anchor2062_20260723"
CELL_ROOT = REPO / "tmp" / "full_h5_anchor2062" / RUN_PREFIX / "reform_full_h5"
BASELINE_CACHE = REPO / "tmp" / "anchor2062_baseline.json"
TARGETS = (REPO / "results.csv", REPO / "dashboard" / "public" / "data" / "results.csv")
SPLICE_REFORMS = ("option12", "option5")
YEAR = 2062
PARENTS = (2060, 2065)
OACT_PIN = {"tob_oasdi": 415.3305, "tob_medicare_hi": 347.5620, "tob_total": 762.8925}

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


def compute_baseline() -> None:
    agg = _agg()
    dataset = CERT / f"projected_datasets_certrepro/{YEAR}.h5"
    print(f"[baseline] {YEAR} computing on {dataset} ...", flush=True)
    b = agg.load_baseline(YEAR, str(dataset))
    BASELINE_CACHE.write_text(
        json.dumps(
            {
                "revenue": b.revenue,
                "tob_medicare_hi": b.tob_medicare_hi,
                "tob_oasdi": b.tob_oasdi,
                "tob_total": b.tob_total,
                "social_security": b.social_security,
                "taxable_payroll": b.taxable_payroll,
                "tax_assumption_name": b.tax_assumption_name,
                "tax_assumption_active": b.tax_assumption_active,
            },
            indent=1,
        )
    )
    print(f"[baseline] revenue={b.revenue / 1e9:,.4f}B tob={b.tob_total / 1e9:,.4f}B")
    print("BASELINE_2062_DONE")


def cached_baseline(agg):
    d = json.loads(BASELINE_CACHE.read_text())
    return agg.BaselineResult(**d)


def exact_row(agg, baseline, reform: str) -> dict:
    scenario = CELL_ROOT / f"year={YEAR}" / f"reform={reform}" / "scenario.h5"
    metadata_path = scenario.parent / "metadata.json"
    if not scenario.exists() or not metadata_path.exists():
        raise RuntimeError(f"missing 2062 cell {reform}; refusing")
    metadata = json.loads(metadata_path.read_text())
    row = agg.build_reform_result_from_aggregates(
        reform_id=reform,
        year=YEAR,
        baseline=baseline,
        reform_totals=agg._aggregate_full_output_h5(scenario),
        employer_net_reforms=agg.MODAL_EMPLOYER_NET_REFORMS,
        default_net_impact_mode="direct",
        scoring_type="static",
    )
    scaled = {column: row[column] / 1e9 for column in DOLLAR_COLUMNS}
    scaled.update(
        {
            "year": YEAR,
            "reform_name": reform,
            "scoring_type": "static",
            "source": "exact_full_h5",
            "full_h5_result_type": "exact_full_h5",
            "run_prefix": RUN_PREFIX,
            "scenario_h5_uri": (
                f"r2://axiom-corpus/crfb/reform_full_h5/{RUN_PREFIX}"
                f"/reform_full_h5/year={YEAR}/reform={reform}/scenario.h5"
            ),
            "metadata_uri": (
                f"r2://axiom-corpus/crfb/reform_full_h5/{RUN_PREFIX}"
                f"/reform_full_h5/year={YEAR}/reform={reform}/metadata.json"
            ),
            "complete_uri": "",
            "output_h5_sha256": metadata["output_h5_sha256"],
            "baseline_source": "certrepro_same_dataset_baseline",
            "baseline_tax_assumption_name": metadata["tax_assumption"]["name"],
            "baseline_tax_assumption_active": str(metadata["tax_assumption"]["active"]),
        }
    )
    return scaled


def run_gate(agg=None, verbose: bool = True) -> dict[str, dict]:
    agg = agg or _agg()
    baseline = cached_baseline(agg)
    failures = []
    for key, want in OACT_PIN.items():
        got = getattr(baseline, key) / 1e9
        ok = abs(got - want) <= 1e-3
        if verbose:
            print(f"[G1] baseline {key}: {got:,.6f}B vs OACT {want:,.4f}B "
                  f"({'OK' if ok else 'FAIL'})")
        if not ok:
            failures.append(f"G1 {key}")
    rows = {r: exact_row(agg, baseline, r) for r in ("option1", "option12", "option5")}
    o1 = rows["option1"]["revenue_impact"]
    tob = baseline.tob_total / 1e9
    g2 = abs(o1 + tob) <= 0.1
    if verbose:
        print(f"[G2] option1@2062 {o1:+.6f}B vs -baseline TOB {-tob:,.6f}B "
              f"(diff {abs(o1 + tob) * 1000:.3f}M, {'OK' if g2 else 'FAIL'})")
    if not g2:
        failures.append("G2")
    gap = rows["option12"]["revenue_impact"] - rows["option5"]["revenue_impact"]
    g3 = abs(gap) <= 0.5
    if verbose:
        print(f"[G3] option12@2062 {rows['option12']['revenue_impact']:+.6f}B vs "
              f"option5@2062 {rows['option5']['revenue_impact']:+.6f}B "
              f"(gap {gap * 1000:+.3f}M, {'OK' if g3 else 'FAIL'}; "
              f"displayed artifact was +19,543.450M)")
    if not g3:
        failures.append("G3")
    if failures:
        raise SystemExit(f"GATE FAILURES: {failures}")
    if verbose:
        print("[gate] ALL GATES PASS")
    return rows


def splice() -> None:
    agg = _agg()
    new_rows = run_gate(agg, verbose=True)
    for target in TARGETS:
        with target.open() as file:
            reader = csv.DictReader(file)
            columns = reader.fieldnames or []
            rows = list(reader)

        for reform in SPLICE_REFORMS:
            block = {
                int(r["year"]): r
                for r in rows
                if r["reform_name"] == reform and r["scoring_type"] == "static"
            }
            for parent in PARENTS:
                if block[parent]["full_h5_result_type"] != "exact_full_h5":
                    raise RuntimeError(f"{reform} {parent} is not an exact anchor")
            if block[YEAR]["full_h5_result_type"] == "exact_full_h5":
                raise RuntimeError(f"{reform} {YEAR} already exact; refusing")

            anchors = {
                PARENTS[0]: {c: float(block[PARENTS[0]][c]) for c in DOLLAR_COLUMNS},
                YEAR: new_rows[reform],
                PARENTS[1]: {c: float(block[PARENTS[1]][c]) for c in DOLLAR_COLUMNS},
            }
            replacements: dict[int, dict] = {YEAR: dict(new_rows[reform])}
            for left, right in zip(sorted(anchors), sorted(anchors)[1:]):
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
                            "reform_name": reform,
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
                    row["reform_name"] == reform
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
                        f"{reform} {row['year']}: {old_impact:+.4f}B -> "
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
    if mode == "baseline":
        compute_baseline()
    elif mode == "gate":
        run_gate()
    elif mode == "splice":
        splice()
    else:
        raise SystemExit("usage: fix_option12_2062_anchor.py baseline|gate|splice")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

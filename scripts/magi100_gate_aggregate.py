"""Aggregate local full-H5 cells against published baselines; gate sentinels.

Usage (worktree venv, cwd = crfb-cert):
  .venv/bin/python magi100_gate_aggregate.py sentinel   # compare option1/7/8 2030
  .venv/bin/python magi100_gate_aggregate.py rows       # emit magi100 rows json
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path.home() / "PolicyEngine/crfb-cert"))
import importlib.util

spec = importlib.util.spec_from_file_location(
    "agg",
    Path.home() / "PolicyEngine/crfb-cert/scripts/aggregate_reform_full_h5_results.py",
)
agg = importlib.util.module_from_spec(spec)
sys.modules["agg"] = agg
spec.loader.exec_module(agg)

MAIN = Path.home() / "PolicyEngine/crfb-tob-impacts"
ROOT = MAIN / "tmp/full_h5_magi100/magi100_certrepro_20260706/reform_full_h5"
RESULTS = MAIN / "dashboard/public/data/results.csv"

import pandas as pd  # noqa: E402


def published_baseline_dollars(year: int):
    frame = pd.read_csv(RESULTS)
    frame = frame[(frame.year == year) & (frame.scoring_type == "static")]
    row = frame.iloc[0]
    return agg.BaselineResult(
        revenue=float(row.baseline_revenue) * 1e9,
        tob_medicare_hi=float(row.baseline_tob_medicare_hi) * 1e9,
        tob_oasdi=float(row.baseline_tob_oasdi) * 1e9,
        tob_total=float(row.baseline_tob_total) * 1e9,
        social_security=0.0,
        taxable_payroll=0.0,
        tax_assumption_name=str(row.baseline_tax_assumption_name),
        tax_assumption_active=bool(row.baseline_tax_assumption_active),
    )


def cell_row(year: int, reform: str):
    scenario = ROOT / f"year={year}" / f"reform={reform}" / "scenario.h5"
    totals = agg._aggregate_full_output_h5(scenario)
    row = agg.build_reform_result_from_aggregates(
        reform_id=reform,
        year=year,
        baseline=published_baseline_dollars(year),
        reform_totals=totals,
        employer_net_reforms=agg.MODAL_EMPLOYER_NET_REFORMS,
        default_net_impact_mode="direct",
        scoring_type="static",
    )
    return row


if sys.argv[1] == "sentinel":
    expected = {"option1": -159.411, "option7": 0.000, "option8": 93.725}
    ok = True
    for reform, want in expected.items():
        row = cell_row(2030, reform)
        got = row["revenue_impact"] / 1e9
        diff = abs(got - want)
        print(
            f"[sentinel] {reform} 2030: {got:.3f}B vs published {want:.3f}B (diff {diff * 1000:.1f}M)"
        )
        ok &= diff < 0.01
    print("[sentinel]", "ALL EXACT" if ok else "MISMATCH")
    sys.exit(0 if ok else 1)

if sys.argv[1] == "rows":
    out = []
    for cell in sorted(ROOT.glob("year=*/reform=magi100/scenario.h5")):
        year = int(cell.parent.parent.name.split("=")[1])
        row = cell_row(year, "magi100")
        out.append(row)
        print(f"magi100 {year}: revenue_impact {row['revenue_impact'] / 1e9:,.2f}B")
    dest = MAIN / "tmp/magi100_rows_dollars.json"
    dest.write_text(json.dumps(out, indent=1, default=float))
    print(f"wrote {dest} ({len(out)} rows)")

if sys.argv[1] == "baselines":
    # Compute self-consistent certrepro baselines per year (certified worktree
    # code path: resolves the dataset's own tax-assumption reform).
    cache = MAIN / "tmp/magi100_certrepro_baselines.json"
    done = json.loads(cache.read_text()) if cache.exists() else {}
    years = sorted(
        int(p.parent.parent.name.split("=")[1])
        for p in ROOT.glob("year=*/reform=magi100/scenario.h5")
    )
    for year in years:
        if str(year) in done:
            print(f"[baseline] {year} cached, skip")
            continue
        print(f"[baseline] {year} computing...", flush=True)
        b = agg.load_baseline(
            year,
            str(
                Path.home()
                / f"PolicyEngine/crfb-cert/projected_datasets_certrepro/{year}.h5"
            ),
        )
        done[str(year)] = {
            "revenue": b.revenue,
            "tob_medicare_hi": b.tob_medicare_hi,
            "tob_oasdi": b.tob_oasdi,
            "tob_total": b.tob_total,
            "social_security": b.social_security,
            "taxable_payroll": b.taxable_payroll,
            "tax_assumption_name": b.tax_assumption_name,
            "tax_assumption_active": b.tax_assumption_active,
        }
        cache.write_text(json.dumps(done, indent=1))
        print(f"[baseline] {year} revenue={b.revenue / 1e9:,.1f}B", flush=True)
    print("[baseline] ALL BASELINES DONE")

if sys.argv[1] == "rows2":
    # Self-consistent rows: certrepro reform leg minus certrepro baseline.
    cache = json.loads((MAIN / "tmp/magi100_certrepro_baselines.json").read_text())
    pub = pd.read_csv(RESULTS)
    pub = pub[pub.scoring_type == "static"]
    out = []
    for cell in sorted(ROOT.glob("year=*/reform=magi100/scenario.h5")):
        year = int(cell.parent.parent.name.split("=")[1])
        c = cache[str(year)]
        baseline = agg.BaselineResult(
            revenue=c["revenue"],
            tob_medicare_hi=c["tob_medicare_hi"],
            tob_oasdi=c["tob_oasdi"],
            tob_total=c["tob_total"],
            social_security=c["social_security"],
            taxable_payroll=c["taxable_payroll"],
            tax_assumption_name=c["tax_assumption_name"],
            tax_assumption_active=c["tax_assumption_active"],
        )
        totals = agg._aggregate_full_output_h5(cell)
        row = agg.build_reform_result_from_aggregates(
            reform_id="magi100",
            year=year,
            baseline=baseline,
            reform_totals=totals,
            employer_net_reforms=agg.MODAL_EMPLOYER_NET_REFORMS,
            default_net_impact_mode="direct",
            scoring_type="static",
        )
        pub_base = float(pub[pub.year == year].iloc[0]["baseline_revenue"])
        drift = (c["revenue"] / 1e9 / pub_base - 1) * 100
        print(
            f"magi100 {year}: impact {row['revenue_impact'] / 1e9:,.2f}B  (baseline drift vs published {drift:+.2f}%)"
        )
        out.append(row)
    dest = MAIN / "tmp/magi100_rows_dollars.json"
    dest.write_text(json.dumps(out, indent=1, default=float))
    print(f"wrote {dest} ({len(out)} rows)")
